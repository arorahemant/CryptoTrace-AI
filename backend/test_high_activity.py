"""Replay public Mainnet observations. No network or fabricated fallback records."""
import copy
import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from app.engines.trace_engine import TraceEngine
from app.providers.alchemy import AlchemyEthereumProvider, ProviderFailure
from app.providers.demo import DemoProvider

CAPTURE = json.loads((Path(__file__).parent / 'tests/fixtures/high_activity_alchemy.json').read_text())
ADDRESS = CAPTURE['summary']['address']
START, END = CAPTURE['summary']['from_block'], CAPTURE['summary']['to_block']


class Replay:
    def __init__(self):
        self.entries = copy.deepcopy(CAPTURE['responses'])
        self.calls = []

    async def __call__(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        matches = [e for e in self.entries if e['method'] == method and e['params'] == params]
        assert matches, 'Uncaptured request: replay must not invent empty results'
        entry = matches[0]
        if 'failure' in entry:
            raise ProviderFailure(entry['failure'])
        return 200, {'jsonrpc': '2.0', 'id': 1, 'result': copy.deepcopy(entry['result'])}, None


async def trace(replay=None, **options):
    provider = AlchemyEthereumProvider(transport=replay or Replay(), api_key=SecretStr('fixture-only'))
    return await TraceEngine(provider).trace(ADDRESS, chain='ethereum', from_block=START, to_block=END, **options)


@pytest.mark.asyncio
async def test_captured_high_activity_pages_exact_events_and_partial_boundary(monkeypatch):
    def forbid_demo(*args, **kwargs):
        raise AssertionError('Ethereum must never fall back to DemoProvider')
    monkeypatch.setattr(DemoProvider, '__init__', forbid_demo)
    replay = Replay()
    result = await trace(replay)
    records, wallets = result['transactions'], result['wallets']
    assert len(records) == len(wallets) == 62
    assert len({r['hash'] for r in records}) == 4
    assert len({r['transfer_id'] for r in records}) == 62
    expected = {r['transfer_id']: r for r in CAPTURE['transactions']}
    for record in records:
        original = expected[record['transfer_id']]
        for field in ('amount_base_units', 'amount_exact', 'token_decimals', 'asset_id', 'log_index', 'block_hash', 'transaction_status'):
            assert record[field] == original[field]
        assert START <= record['block_number'] <= END
        assert record['source'] == 'alchemy_ethereum'
        assert record['provenance']['pinned_end_block'] == END
        assert not record['is_suspicious']
    assert all(not w['is_suspicious'] and not w.get('vasp_name') for w in wallets.values())
    coverage = result['stats']['coverage']
    assert coverage['partial'] and not coverage['exhausted']
    assert coverage['provider_errors'] == [{'code': 'timeout'}]
    assert coverage['provider_requests'] == 29 <= 200
    assert coverage['observation_boundaries']['max_hops'] == 2
    pages = [e for e in replay.entries if e['method'] == 'alchemy_getAssetTransfers' and e['params'][0].get('fromAddress') == ADDRESS]
    assert [len(p['result']['transfers']) for p in pages] == [25, 25, 12]
    assert pages[1]['params'][0]['pageKey'] == pages[0]['result']['pageKey']
    assert pages[2]['params'][0]['pageKey'] == pages[1]['result']['pageKey']
    assert not pages[2]['result'].get('pageKey')


@pytest.mark.asyncio
async def test_duplicate_captured_events_do_not_inflate_graph():
    replay = Replay()
    page = next(e for e in replay.entries if e['method'] == 'alchemy_getAssetTransfers')
    page['result']['transfers'].append(copy.deepcopy(page['result']['transfers'][0]))
    result = await trace(replay)
    assert len(result['transactions']) == len(result['wallets']) == 62
    assert {r['transfer_id'] for r in result['transactions']} == {r['transfer_id'] for r in CAPTURE['transactions']}


@pytest.mark.asyncio
async def test_high_activity_transfer_limit_stops_at_captured_page_boundary():
    replay = Replay()
    result = await trace(replay, max_transactions=50)
    assert len(result['transactions']) == 50
    coverage = result['stats']['coverage']
    assert coverage['partial'] and coverage['state'] == 'provider_limit'
    assert not coverage['exhausted']
    assert len([1 for m, _ in replay.calls if m == 'alchemy_getAssetTransfers']) == 2


@pytest.mark.asyncio
async def test_failed_next_page_preserves_only_observed_records():
    replay = Replay()
    page = next(e for e in replay.entries if e['method'] == 'alchemy_getAssetTransfers' and e['params'][0].get('pageKey'))
    page.pop('result')
    page['failure'] = 'provider_limit'
    result = await trace(replay)
    assert len(result['transactions']) == 25
    assert result['stats']['coverage']['partial']
    assert result['stats']['coverage']['state'] == 'provider_limit'


def test_capture_authenticated_pipeline_has_one_run_and_no_manufactured_findings():
    graph, capability, report = CAPTURE['graph'], CAPTURE['capability'], CAPTURE['report']
    assert CAPTURE['intake_capability']['data_origin'] == 'none'
    assert capability['data_origin'] == 'observed'
    assert graph['run_id'] == capability['run_id'] == report['capability']['run_id']
    assert graph['destination']['address'] == capability['destination']['address']
    assert {e['id'] for e in graph['edges']} == {r['transfer_id'] for r in CAPTURE['transactions']}
    assert CAPTURE['summary']['findings'] == 0
    assert CAPTURE['summary']['evidence'] == 62
    assert CAPTURE['summary']['recommendations'] == 1
    serialized = json.dumps(CAPTURE)
    assert 'alchemy.com/v2/' not in serialized and 'Bearer ' not in serialized


@pytest.mark.asyncio
async def test_replay_rejects_uncaptured_requests_instead_of_synthetic_fallback():
    with pytest.raises(AssertionError, match='Uncaptured request'):
        await Replay()('alchemy_getAssetTransfers', [{'fromAddress': 'not-captured'}])
