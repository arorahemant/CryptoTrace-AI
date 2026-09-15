"""Read-only Ethereum Mainnet observations through Alchemy. No identity intelligence."""
import asyncio
import re
import time
from datetime import datetime, timezone

import aiohttp

from app.core.config import settings
from app.core.transfers import normalize_transfer
from app.providers.base import BlockchainProvider, ProviderPage

TRANSFER_TOPIC = '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef'
ADDRESS = re.compile(r'0x[0-9a-fA-F]{40}\Z')
HASH = re.compile(r'0x[0-9a-fA-F]{64}\Z')


class ProviderFailure(Exception):
    """Only fixed, credential-free codes may cross the provider boundary."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def quantity(value):
    if not isinstance(value, str) or not re.fullmatch(r'0x[0-9a-fA-F]+', value):
        raise ProviderFailure('malformed_response')
    number = int(value, 16)
    if number >= 2**256:
        raise ProviderFailure('malformed_response')
    return number


def address(value):
    if not isinstance(value, str) or not ADDRESS.fullmatch(value):
        raise ProviderFailure('malformed_response')
    return value.lower()


def tx_hash(value):
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ProviderFailure('malformed_response')
    return value.lower()


class AlchemyEthereumProvider(BlockchainProvider):
    provider_name = 'alchemy_ethereum'
    is_demo = False
    max_requests = 200
    timeout = 10
    retries = 2

    def __init__(self, *, transport=None, api_key=None, sleep=asyncio.sleep):
        self._key = settings.ALCHEMY_API_KEY if api_key is None else api_key
        self._transport = transport
        self._sleep = sleep
        self.requests = 0
        self.deadline = None
        self._session = None
        self._cache = {}
        self.start_block = None
        self.end_block = None
        self.requested_range = {}

    async def __aenter__(self):
        self.deadline = time.monotonic() + self.timeout
        if self._transport is None:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, *args):
        if self._session:
            await self._session.close()

    def _credential(self):
        value = self._key.get_secret_value() if hasattr(self._key, 'get_secret_value') else self._key
        if not value:
            raise ProviderFailure('not_configured')
        return value

    async def _send(self, method, params):
        # aiohttp does not log outbound URLs. Never log exceptions, bodies, or headers.
        async with self._session.post(
            'https://eth-mainnet.g.alchemy.com/v2/' + self._credential(),
            json={'jsonrpc': '2.0', 'id': self.requests, 'method': method, 'params': params},
            allow_redirects=False,
        ) as response:
            retry_after = response.headers.get('Retry-After')
            if response.status != 200:
                return response.status, {}, retry_after
            body = await response.json(content_type=None)
            if not isinstance(body, dict) or body.get('jsonrpc') != '2.0' or body.get('id') != self.requests:
                raise ProviderFailure('malformed_response')
            return response.status, body, retry_after

    async def rpc(self, method, params):
        self._credential()
        for attempt in range(self.retries + 1):
            if self.requests >= self.max_requests:
                raise ProviderFailure('provider_limit')
            remaining = self.deadline - time.monotonic() if self.deadline else self.timeout
            if remaining <= 0:
                raise ProviderFailure('timeout')
            self.requests += 1
            retry_after = None
            try:
                async with asyncio.timeout(min(self.timeout, remaining)):
                    status, body, retry_after = await (self._transport(method, params) if self._transport else self._send(method, params))
                if status in (401, 403):
                    raise ProviderFailure('invalid_credentials')
                if status == 429:
                    code = 'provider_limit'
                elif status >= 500:
                    code = 'unavailable'
                elif status != 200 or not isinstance(body, dict):
                    raise ProviderFailure('malformed_response')
                elif 'error' in body:
                    error = body['error']
                    n = error.get('code') if isinstance(error, dict) else None
                    code = 'provider_limit' if n == 429 else 'unavailable'
                    if n in (-32600, -32601, -32602):
                        raise ProviderFailure('unavailable')
                elif 'result' not in body:
                    raise ProviderFailure('malformed_response')
                else:
                    return body['result']
            except (TimeoutError, asyncio.TimeoutError):
                code = 'timeout'
            except aiohttp.ClientError:
                code = 'unavailable'
            except (ValueError, TypeError):
                raise ProviderFailure('malformed_response') from None
            if attempt == self.retries:
                raise ProviderFailure(code)
            delay = 0.25 * 2**attempt
            if retry_after is not None:
                try:
                    delay = max(delay, float(retry_after))
                except (ValueError, TypeError):
                    pass
            if self.deadline and delay >= self.deadline - time.monotonic():
                raise ProviderFailure(code)
            await self._sleep(delay)
        raise ProviderFailure('unavailable')

    async def prepare(self, from_block, to_block=None):
        self.requested_range = {'from_block': from_block, 'to_block': to_block, 'end_policy': 'finalized' if to_block is None else 'explicit'}
        if quantity(await self.rpc('eth_chainId', [])) != 1:
            raise ProviderFailure('chain_mismatch')
        head = await self.rpc('eth_getBlockByNumber', ['finalized', False])
        if not isinstance(head, dict):
            raise ProviderFailure('unavailable')
        finalized = quantity(head.get('number'))
        if from_block is None or from_block < 0 or (to_block is not None and to_block < from_block):
            raise ProviderFailure('invalid_block_range')
        self.end_block = finalized if to_block is None else to_block
        self.start_block = from_block
        if self.end_block > finalized or self.start_block > self.end_block:
            raise ProviderFailure('invalid_block_range')
        self.pinned_hash = tx_hash((await self.block(self.end_block)).get('hash'))

    async def block(self, number):
        key = ('block', number)
        if key not in self._cache:
            result = await self.rpc('eth_getBlockByNumber', [hex(number), False])
            if not isinstance(result, dict) or quantity(result.get('number')) != number:
                raise ProviderFailure('historical_data_unavailable')
            tx_hash(result.get('hash'))
            quantity(result.get('timestamp'))
            self._cache[key] = result
        return self._cache[key]

    async def transaction_receipt(self, hash_value):
        key = ('receipt', hash_value)
        if key not in self._cache:
            tx = await self.rpc('eth_getTransactionByHash', [hash_value])
            receipt = await self.rpc('eth_getTransactionReceipt', [hash_value])
            if not isinstance(tx, dict) or not isinstance(receipt, dict):
                raise ProviderFailure('historical_data_unavailable')
            if tx_hash(tx.get('hash')) != hash_value or tx_hash(receipt.get('transactionHash')) != hash_value:
                raise ProviderFailure('malformed_response')
            number = quantity(receipt.get('blockNumber'))
            if not self.start_block <= number <= self.end_block or quantity(tx.get('blockNumber')) != number:
                raise ProviderFailure('block_boundary_mismatch')
            block = await self.block(number)
            if receipt.get('blockHash') != block['hash'] or tx.get('blockHash') != block['hash']:
                raise ProviderFailure('block_boundary_mismatch')
            if quantity(receipt.get('status')) != 1:
                raise ProviderFailure('transaction_failed')
            if not isinstance(receipt.get('logs'), list):
                raise ProviderFailure('malformed_response')
            self._cache[key] = tx, receipt, block
        return self._cache[key]

    async def decimals(self, contract, number):
        key = ('decimals', contract, number)
        if key not in self._cache:
            try:
                raw = await self.rpc('eth_call', [{'to': contract, 'data': '0x313ce567'}, hex(number)])
            except ProviderFailure as exc:
                if exc.code in ('timeout', 'provider_limit', 'invalid_credentials', 'not_configured'):
                    raise
                raise ProviderFailure('metadata_unavailable') from None
            if not isinstance(raw, str) or not HASH.fullmatch(raw) or quantity(raw) > 255:
                raise ProviderFailure('metadata_unavailable')
            self._cache[key] = quantity(raw)
        return self._cache[key]

    async def fetch_page(self, wallet, direction, continuation=None, limit=25):
        now = datetime.now(timezone.utc).isoformat()
        page = ProviderPage(retrieved_at=now, requested_block_range=dict(self.requested_range),
            provenance={'provider': self.provider_name, 'network': 'ethereum_mainnet', 'chain_id': 1},
            observation_boundaries={'from_block': self.start_block, 'to_block': self.end_block,
                'end_block_hash': self.pinned_hash, 'direction': direction, 'address': wallet,
                'categories': ['external', 'erc20']})
        try:
            query = {'fromBlock': hex(self.start_block), 'toBlock': hex(self.end_block),
                'fromAddress' if direction == 'outgoing' else 'toAddress': address(wallet),
                'category': ['external', 'erc20'], 'excludeZeroValue': True, 'withMetadata': True,
                'order': 'asc', 'maxCount': hex(min(25, max(1, limit)))}
            if continuation:
                query['pageKey'] = continuation
            result = await self.rpc('alchemy_getAssetTransfers', [query])
            if not isinstance(result, dict) or not isinstance(result.get('transfers'), list):
                raise ProviderFailure('malformed_response')
            token = result.get('pageKey')
            if token is not None and (not isinstance(token, str) or len(token) > 1024):
                raise ProviderFailure('malformed_response')
            page.continuation = token or None
            page.exhausted = not page.continuation
            seen = {}
            for item in result['transfers']:
                try:
                    for record in await self._records(item, wallet, direction, now):
                        identity = record['transfer_id']
                        signature = tuple(record[k] for k in ('amount_base_units', 'asset_id', 'from_address', 'to_address', 'block_hash'))
                        if identity in seen and seen[identity] != signature:
                            raise ProviderFailure('conflicting_event')
                        if identity not in seen:
                            seen[identity] = signature
                            page.records.append(record)
                except ProviderFailure as exc:
                    page.errors.append({'code': exc.code})
                    page.partial_coverage = True
                    if exc.code in ('timeout', 'provider_limit', 'invalid_credentials'):
                        break
                except (KeyError, TypeError, ValueError, OverflowError):
                    page.errors.append({'code': 'malformed_response'})
                    page.partial_coverage = True
        except ProviderFailure as exc:
            page.errors.append({'code': exc.code})
            page.partial_coverage = True
            page.exhausted = False
        return page

    async def _records(self, item, wallet, direction, now):
        if not isinstance(item, dict) or item.get('category') not in ('external', 'erc20'):
            raise ProviderFailure('malformed_response')
        hash_value = tx_hash(item.get('hash'))
        tx, receipt, block = await self.transaction_receipt(hash_value)
        number = quantity(receipt['blockNumber'])
        if quantity(item.get('blockNum')) != number:
            raise ProviderFailure('block_boundary_mismatch')
        sender, recipient = address(item.get('from')), address(item.get('to'))
        if (sender if direction == 'outgoing' else recipient) != wallet:
            raise ProviderFailure('malformed_response')
        base = {'hash': hash_value, 'chain_id': 'ethereum', 'block_number': number,
            'block_hash': block['hash'], 'transaction_status': 1, 'status': 'confirmed',
            'timestamp': datetime.fromtimestamp(quantity(block['timestamp']), timezone.utc),
            'source': self.provider_name, 'is_suspicious': False,
            'provenance': {'provider': self.provider_name, 'chain_id': 1, 'retrieved_at': now,
                'methods': ['alchemy_getAssetTransfers', 'eth_getTransactionByHash', 'eth_getTransactionReceipt', 'eth_getBlockByNumber'],
                'requested_block_range': self.requested_range, 'pinned_end_block': self.end_block,
                'pinned_end_block_hash': self.pinned_hash}}
        if item['category'] == 'external':
            if address(tx.get('from')) != sender or address(tx.get('to')) != recipient:
                raise ProviderFailure('malformed_response')
            return [normalize_transfer({**base, 'from_address': sender, 'to_address': recipient,
                'asset': 'ETH', 'asset_id': 'ethereum:native', 'event_index': 'native',
                'amount_base_units': str(quantity(tx.get('value'))), 'token_decimals': 18}, 'ethereum')]
        raw = item.get('rawContract')
        if not isinstance(raw, dict):
            raise ProviderFailure('metadata_unavailable')
        contract = address(raw.get('address'))
        decimals = await self.decimals(contract, number)
        records = []
        for log in receipt['logs']:
            if not isinstance(log, dict):
                raise ProviderFailure('malformed_response')
            topics = log.get('topics', [])
            if log.get('address', '').lower() != contract or not topics or topics[0] != TRANSFER_TOPIC:
                continue
            if len(topics) != 3 or not HASH.fullmatch(log.get('data', '')):
                raise ProviderFailure('malformed_response')
            if any(not HASH.fullmatch(t) or t[2:26] != '0'*24 for t in topics[1:]):
                raise ProviderFailure('malformed_response')
            source, target = address('0x'+topics[1][-40:]), address('0x'+topics[2][-40:])
            if source != sender or target != recipient:
                continue
            if log.get('removed') is not False or log.get('transactionHash') != hash_value or log.get('blockHash') != block['hash'] or quantity(log.get('blockNumber')) != number:
                raise ProviderFailure('block_boundary_mismatch')
            index = quantity(log.get('logIndex'))
            records.append(normalize_transfer({**base, 'from_address': source, 'to_address': target,
                'asset': 'ERC-20', 'asset_id': 'ethereum:token:'+contract, 'token_contract': contract,
                'event_index': str(index), 'log_index': index, 'amount_base_units': str(quantity(log['data'])),
                'token_decimals': decimals, 'provenance': {**base['provenance'], 'decimals_source': 'eth_call:decimals()', 'decimals_block': number}}, 'ethereum'))
        if not records:
            raise ProviderFailure('receipt_event_mismatch')
        return records

    async def validate_address(self, value, chain):
        return chain == 'ethereum' and bool(ADDRESS.fullmatch(value))

    async def get_network(self, value):
        return 'ethereum' if ADDRESS.fullmatch(value) else None

    async def get_transactions(self, address, chain, **kwargs):
        raise ProviderFailure('bounded_page_required')

    async def get_transaction(self, hash_value, chain):
        if chain != 'ethereum':
            raise ProviderFailure('chain_mismatch')
        return await self.rpc('eth_getTransactionByHash', [tx_hash(hash_value)])

    async def get_balance(self, address, chain):
        raise ProviderFailure('outside_observation_scope')
