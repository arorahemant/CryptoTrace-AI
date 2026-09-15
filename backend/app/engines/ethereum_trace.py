"""Bounded breadth-first observations, never a claim of exhaustive fund custody."""
from dataclasses import asdict
from collections import deque
from datetime import datetime, timezone

from app.core.transfers import asset_totals
from app.providers.alchemy import ProviderFailure


async def trace_ethereum(provider, starting_address, *, max_hops=2, max_transactions=100,
                         direction='outgoing', from_block=None, to_block=None):
    from app.engines.trace_engine import TraceEngine
    max_hops, max_transactions = min(max_hops, 2), min(max_transactions, 100)
    origin = starting_address.lower()
    wallets, records, paths, pages, errors = {}, {}, [], [], []
    decimals_by_asset = {}
    def register(value, hop):
        wallets.setdefault(value, {'address': value, 'is_reported': value == origin,
            'is_suspicious': False, 'is_destination': False, 'is_intermediary': False,
            'hop_distance': hop, 'transaction_count': 0, 'expansion_state': 'pending'})
    register(origin, 0)
    queue = deque([(origin, 0, [origin])])
    visited = set()
    connected = False
    stopped = False
    try:
        async with provider:
            await provider.prepare(from_block, to_block)
            connected = True
            while queue and len(records) < max_transactions and not stopped:
                wallet, hop, path = queue.popleft()
                if wallet in visited:
                    continue
                visited.add(wallet)
                if hop >= max_hops:
                    wallets[wallet]['expansion_state'] = 'hop_limit'
                    paths.append(path)
                    continue
                wallets[wallet]['expansion_state'] = 'expanded'
                for flow in (['outgoing', 'incoming'] if direction == 'both' else [direction]):
                    token, seen_tokens = None, set()
                    while len(records) < max_transactions:
                        page = await provider.fetch_page(wallet, flow, token, min(25, max_transactions-len(records)))
                        summary = asdict(page)
                        summary.pop('records')
                        summary['record_count'] = len(page.records)
                        pages.append(summary)
                        errors.extend(page.errors)
                        stopped = any(e["code"] in {"invalid_credentials", "not_configured", "timeout", "provider_limit"} for e in page.errors)
                        if page.partial_coverage:
                            wallets[wallet]['expansion_state'] = 'provider_error'
                        for record in page.records:
                            identity = record['transfer_id']
                            prior = records.get(identity)
                            signature = ('from_address', 'to_address', 'asset_id', 'amount_base_units', 'token_decimals', 'block_hash')
                            if (prior and any(prior[k] != record[k] for k in signature)) or (
                                record['asset_id'] in decimals_by_asset and decimals_by_asset[record['asset_id']] != record['token_decimals']):
                                errors.append({'code': 'conflicting_event'})
                                wallets[wallet]['expansion_state'] = 'provider_error'
                                continue
                            if prior:
                                continue
                            if len(records) >= max_transactions:
                                wallets[wallet]['expansion_state'] = 'transaction_limit'
                                break
                            decimals_by_asset[record['asset_id']] = record['token_decimals']
                            record['hop_number'] = hop + 1
                            records[identity] = record
                            neighbor = record['to_address'] if flow == 'outgoing' else record['from_address']
                            register(neighbor, hop + 1)
                            queue.append((neighbor, hop + 1, path + [neighbor]))
                        if page.errors or page.exhausted:
                            break
                        if not page.continuation or page.continuation in seen_tokens:
                            errors.append({'code': 'pagination_stalled'})
                            wallets[wallet]['expansion_state'] = 'provider_error'
                            break
                        token = page.continuation
                        seen_tokens.add(token)
                    if stopped:
                        break
                    if len(records) >= max_transactions:
                        wallets[wallet]['expansion_state'] = 'transaction_limit'
                        break
                paths.append(path)
    except ProviderFailure as exc:
        errors.append({'code': exc.code})
        wallets[origin]['expansion_state'] = 'provider_error'
    except Exception:
        # Never expose a transport exception (which may embed credentials).
        errors.append({'code': 'unavailable'})
        wallets[origin]['expansion_state'] = 'provider_error'
    transactions = sorted(records.values(), key=lambda r: (r['timestamp'], r['transfer_id']))
    for wallet in wallets.values():
        if wallet['expansion_state'] == 'pending':
            wallet['expansion_state'] = 'provider_error' if stopped else 'transaction_limit'
    TraceEngine(provider)._finalize_wallet_metadata(wallets, transactions)
    partial = bool(errors) or any(w['expansion_state'] != 'expanded' for w in wallets.values())
    codes = {e['code'] for e in errors}
    state = ('not_configured' if 'not_configured' in codes else
             'invalid_credentials' if 'invalid_credentials' in codes else
             'provider_limit' if 'provider_limit' in codes or len(records) >= max_transactions else
             'metadata_unavailable' if 'metadata_unavailable' in codes else
             'partial' if transactions and partial else
             'unavailable' if errors else 'observed' if transactions else 'connected_no_records')
    coverage = {'state': state, 'partial': partial, 'exhausted': not partial,
        'requested_block_range': provider.requested_range or {'from_block': from_block, 'to_block': to_block},
        'observation_boundaries': {'from_block': provider.start_block, 'to_block': provider.end_block,
            'end_block_hash': getattr(provider, 'pinned_hash', None), 'categories': ['external', 'erc20'],
            'max_hops': max_hops, 'max_transfers': max_transactions, 'direction': direction},
        'retrieved_at': datetime.now(timezone.utc).isoformat(), 'provider_errors': errors,
        'pages': pages, 'provider_requests': provider.requests,
        'provenance': {'provider': provider.provider_name, 'chain_id': 1, 'network': 'ethereum_mainnet'},
        'limits': {'max_provider_requests': 200, 'timeout_seconds': 10, 'timeout_scope': 'whole_observation_run', 'retries': 2, 'concurrency': 1},
        'limitations': ['bounded_historical_observation', 'external_eth_and_standard_erc20_only',
            'no_internal_eth_nfts_bridges_or_swap_interpretation', 'no_ownership_or_fraud_confirmation',
            'no_vasp_verification_or_external_action', 'not_continuous_monitoring', 'fraud_patterns_and_risk_scoring_not_enabled', 'structural_routes_not_proven_fund_continuity']}
    return {'transactions': transactions, 'wallets': wallets, 'paths': paths, 'stats': {
        'total_transactions': len(transactions), 'total_wallets': len(wallets),
        'max_hop_reached': max((t['hop_number'] for t in transactions), default=0),
        'total_amount_traced': None, 'transfer_volume_by_asset': asset_totals(transactions),
        'origin_outflow_by_asset': asset_totals(t for t in transactions if t['from_address'] == origin),
        'provider': provider.provider_name, 'is_demo': False, 'provider_errors': len(errors),
        'malformed_transactions': sum(e['code'] == 'malformed_response' for e in errors),
        'trace_status': 'partial' if partial else 'complete',
        'trace_warning': 'Observation is incomplete; inspect coverage boundaries.' if partial else None,
        'coverage': coverage, 'provider_connected': connected}}
