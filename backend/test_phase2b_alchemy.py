"""Phase 2B regression: captured benign public examples and fault injection."""
import asyncio
import copy
import json
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings, Settings
from app.core.capabilities import capability_for
from app.core.transfers import asset_totals
from app.providers.alchemy import AlchemyEthereumProvider, ProviderFailure, TRANSFER_TOPIC
from app.providers.demo import DemoProvider
from app.providers import get_provider
from app.engines.trace_engine import TraceEngine
from app.models.models import Case, Blockchain, Transaction, User, Evidence
from app.services.investigation_service import InvestigationService
from app.services.recommendation_service import build_recommendations
from app.services.destination_service import destination_context
from app.api.asset_actions import _case_context
from app.api.cases import get_transactions, get_evidence, generate_report, get_report, investigate
from app.schemas.schemas import InvestigateRequest
from test_p0_remediation import investigation_session_factory, _create_demo_case

ETH_ADDRESS = '0xef4396d9ff8107086d215a1c9f8866c54795d7c7'
RECIPIENT = '0x4e83362442b8d1bec281594cea3050c8eb01311c'
ERC_TX = '0xe8c208398bd5ae8e4c237658580db56a2a94dfa0ca382c99b776fa6e7d31d5b4'
ETH_TX = '0x3847245c01829b043431067fb2bfa95f7b5bdc7e4246c843e7a573ab6f26f5ff'
MKR = '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2'
BLOCK = 4730207
ETH_BLOCK = 11594460
FIXTURE = json.loads((Path(__file__).parent / 'tests/fixtures/phase2b_alchemy.json').read_text())


class CapturedTransport:
    def __init__(self):
        self.calls = []
        self.entries = copy.deepcopy(FIXTURE['responses'])
        self.override = None

    def result(self, method, params):
        return copy.deepcopy(next(e['result'] for e in self.entries if e['method'] == method and e['params'] == params))

    async def __call__(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if self.override:
            value = self.override(method, params)
            if value is not None:
                return value
        if method == 'eth_chainId':
            result = '0x1'
        elif method == 'eth_getBlockByNumber' and params[0] == 'finalized':
            result = {'number': hex(ETH_BLOCK + 1)}
        elif method == 'alchemy_getAssetTransfers':
            query = params[0]
            direction = 'fromAddress' if 'fromAddress' in query else 'toAddress'
            matches = [e for e in self.entries if e['method'] == method and
                e['params'][0].get(direction) == query[direction] and
                e['params'][0]['fromBlock'] == query['fromBlock']]
            result = copy.deepcopy(matches[0]['result']) if matches else {'transfers': []}
            # Replay only the documented ETH example whose receipt was captured.
            if query.get('fromAddress') == ETH_ADDRESS:
                result['transfers'] = [r for r in result['transfers'] if r['hash'] == ETH_TX]
        else:
            result = self.result(method, params)
        return 200, {'jsonrpc': '2.0', 'id': 1, 'result': result}, None


def provider(transport=None, **kwargs):
    return AlchemyEthereumProvider(transport=transport or CapturedTransport(), api_key=SecretStr('fixture-only'), **kwargs)


@pytest.mark.asyncio
async def test_captured_eth_exact_wei_provenance_and_historical_boundary():
    t = CapturedTransport()
    result = await TraceEngine(provider(t)).trace(ETH_ADDRESS, chain='ethereum', from_block=ETH_BLOCK, to_block=ETH_BLOCK)
    assert len(result['transactions']) == 1
    tx = result['transactions'][0]
    assert tx['hash'] == ETH_TX
    assert tx['amount_base_units'] == '500000000000000000'
    assert tx['amount_exact'] == '0.5' and tx['token_decimals'] == 18
    assert tx['asset_id'] == 'ethereum:native' and tx['event_index'] == 'native'
    assert tx['transaction_status'] == 1 and tx['block_hash']
    assert tx['source'] == 'alchemy_ethereum'
    assert tx['provenance']['pinned_end_block'] == ETH_BLOCK
    assert all(not w['is_suspicious'] for w in result['wallets'].values())
    assert not tx['is_suspicious']
    queries = [p[0] for m,p in t.calls if m == 'alchemy_getAssetTransfers']
    assert all(q['fromBlock'] == q['toBlock'] == hex(ETH_BLOCK) for q in queries)
    assert all(q['category'] == ['external','erc20'] for q in queries)


@pytest.mark.asyncio
async def test_captured_erc20_reconciles_receipt_amount_decimals_and_status():
    result = await TraceEngine(provider()).trace(RECIPIENT, chain='ethereum', direction='incoming', from_block=BLOCK, to_block=BLOCK)
    tx = result['transactions'][0]
    assert tx['hash'] == ERC_TX and tx['log_index'] == 25
    assert tx['amount_base_units'] == '5901522149285533025181'
    assert tx['amount_exact'] == '5901.522149285533025181'
    assert tx['asset_id'] == 'ethereum:token:'+MKR
    assert tx['provenance']['decimals_source'] == 'eth_call:decimals()'
    assert tx['provenance']['decimals_block'] == BLOCK


@pytest.mark.asyncio
async def test_captured_multiple_event_receipt_missing_legacy_decimals_is_partial():
    result = await TraceEngine(provider()).trace(RECIPIENT, chain='ethereum', direction='both', from_block=BLOCK, to_block=BLOCK)
    assert len(result['transactions']) == 1
    coverage = result['stats']['coverage']
    assert coverage['partial'] and coverage['state'] == 'metadata_unavailable'
    assert {'code':'metadata_unavailable'} in coverage['provider_errors']


@pytest.mark.asyncio
async def test_multiple_standard_events_same_transaction_preserve_log_identity():
    t = CapturedTransport()
    entry = next(e for e in t.entries if e['method']=='eth_getTransactionReceipt' and e['params']==[ERC_TX])
    log = copy.deepcopy(next(l for l in entry['result']['logs'] if l['address']==MKR))
    log['logIndex'] = '0x1a'
    log['data'] = '0x'+format(2**256-1,'064x')
    entry['result']['logs'].append(log)
    result = await TraceEngine(provider(t)).trace(RECIPIENT, chain='ethereum', direction='incoming', from_block=BLOCK, to_block=BLOCK)
    records = result['transactions']
    assert len(records) == 2 and len({r['transfer_id'] for r in records}) == 2
    assert {r['log_index'] for r in records} == {25,26}
    assert str(2**256-1) in {r['amount_base_units'] for r in records}
    assert asset_totals(records)[0]['amount_base_units'] == str(2**256-1+5901522149285533025181)


@pytest.mark.asyncio
async def test_pagination_continues_deduplicates_and_exhausts():
    t = CapturedTransport()
    original = next(e['result'] for e in t.entries if e['method']=='alchemy_getAssetTransfers' and e['params'][0].get('fromAddress')==ETH_ADDRESS)
    original = {**original, 'transfers': [r for r in original['transfers'] if r['hash'] == ETH_TX]}
    def override(method, params):
        if method=='alchemy_getAssetTransfers' and params[0].get('fromAddress')==ETH_ADDRESS:
            value = copy.deepcopy(original)
            if 'pageKey' not in params[0]: value['pageKey']='fixture-next-page'
            return 200, {'result':value}, None
    t.override=override
    result = await TraceEngine(provider(t)).trace(ETH_ADDRESS, chain='ethereum', from_block=ETH_BLOCK, to_block=ETH_BLOCK)
    assert len(result['transactions']) == 1
    pages=result['stats']['coverage']['pages']
    assert pages[0]['continuation'] and pages[1]['exhausted']
    assert any(p[0].get('pageKey')=='fixture-next-page' for m,p in t.calls if m=='alchemy_getAssetTransfers')


@pytest.mark.asyncio
async def test_repeated_pagination_token_is_partial_not_infinite():
    t=CapturedTransport()
    t.override=lambda m,p: (200, {'result':{'transfers':[], 'pageKey':'same'}}, None) if m=='alchemy_getAssetTransfers' else None
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert {'code':'pagination_stalled'} in r['stats']['coverage']['provider_errors']
    assert len(t.calls)<10


@pytest.mark.asyncio
async def test_connected_empty_is_not_observed_or_failed():
    t=CapturedTransport()
    t.override=lambda m,p: (200, {'result':{'transfers':[]}}, None) if m=='alchemy_getAssetTransfers' else None
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert not r['transactions']
    assert r['stats']['coverage']['state']=='connected_no_records'
    assert r['stats']['coverage']['exhausted']


@pytest.mark.asyncio
@pytest.mark.parametrize('status,code,requests', [(401,'invalid_credentials',1),(403,'invalid_credentials',1),(500,'unavailable',3),(429,'provider_limit',3)])
async def test_authentication_failure_and_retry_limits(status,code,requests):
    async def transport(m,p): return status, {}, None
    async def no_sleep(delay): pass
    p=provider(transport,sleep=no_sleep)
    with pytest.raises(ProviderFailure,match=code):
        await p.rpc('eth_chainId',[])
    assert p.requests==requests


@pytest.mark.asyncio
async def test_retry_success_and_rate_limit_backoff():
    statuses=[429,503,200]; delays=[]
    async def transport(m,p): return statuses.pop(0), {'result':'0x1'}, '0.5'
    async def sleep(delay): delays.append(delay)
    p=provider(transport,sleep=sleep)
    assert await p.rpc('eth_chainId',[])=='0x1'
    assert p.requests==3 and delays==[0.5,0.5]


@pytest.mark.asyncio
async def test_retry_after_beyond_run_deadline_stops_without_extra_traffic():
    async def transport(m,p): return 429, {}, '60'
    p=provider(transport)
    async with p:
        with pytest.raises(ProviderFailure,match='provider_limit'): await p.rpc('eth_chainId',[])
    assert p.requests==1


@pytest.mark.asyncio
async def test_timeout_retries_and_deadline():
    async def transport(m,p): raise TimeoutError('must not escape')
    async def sleep(delay): pass
    p=provider(transport,sleep=sleep)
    with pytest.raises(ProviderFailure,match='timeout'): await p.rpc('eth_chainId',[])
    assert p.requests==3
    p.deadline=time.monotonic()-1
    with pytest.raises(ProviderFailure,match='timeout'): await p.rpc('eth_chainId',[])
    assert p.requests==3


@pytest.mark.asyncio
async def test_request_budget_includes_retries():
    async def transport(m,p): return 500, {}, None
    async def sleep(delay): pass
    p=provider(transport,sleep=sleep); p.max_requests=2
    with pytest.raises(ProviderFailure,match='provider_limit'): await p.rpc('eth_chainId',[])
    assert p.requests==2


@pytest.mark.asyncio
@pytest.mark.parametrize('chain', ['0x89', '0x0', 'garbage', None])
async def test_chain_id_mismatch_stops_before_transfer_request(chain):
    t=CapturedTransport(); t.override=lambda m,p:(200,{'result':chain},None)
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert not r['transactions'] and len(t.calls)==1
    assert r['stats']['coverage']['state']=='unavailable'


@pytest.mark.asyncio
@pytest.mark.parametrize('bad', [None, '0x', '0x12', '0x'+'f'*64, {}, 18])
async def test_missing_or_malformed_decimals_never_guess(bad):
    t=CapturedTransport(); t.override=lambda m,p:(200,{'result':bad},None) if m=='eth_call' else None
    r=await TraceEngine(provider(t)).trace(RECIPIENT,chain='ethereum',direction='incoming',from_block=BLOCK,to_block=BLOCK)
    assert not r['transactions'] and r['stats']['coverage']['state']=='metadata_unavailable'


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation', ['block_number','block_hash','status','log_index','removed','topics'])
async def test_receipt_reconciliation_rejects_malformed_events(mutation):
    t=CapturedTransport()
    rec=next(e['result'] for e in t.entries if e['method']=='eth_getTransactionReceipt' and e['params']==[ERC_TX])
    log=next(l for l in rec['logs'] if l['address']==MKR)
    if mutation=='block_number': rec['blockNumber']=hex(BLOCK+1)
    if mutation=='block_hash': rec['blockHash']='0x'+'0'*64
    if mutation=='status': rec['status']='0x0'
    if mutation=='log_index': log['logIndex']=None
    if mutation=='removed': log['removed']=True
    if mutation=='topics': log['topics'].append('0x'+'0'*64)
    r=await TraceEngine(provider(t)).trace(RECIPIENT,chain='ethereum',direction='incoming',from_block=BLOCK,to_block=BLOCK)
    assert not r['transactions'] and r['stats']['coverage']['partial']


@pytest.mark.asyncio
async def test_unfinalized_interval_is_rejected():
    t=CapturedTransport()
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK+2)
    assert {'code':'invalid_block_range'} in r['stats']['coverage']['provider_errors']
    assert all(m!='alchemy_getAssetTransfers' for m,p in t.calls)


@pytest.mark.asyncio
async def test_hop_and_transfer_caps_are_enforced():
    r=await TraceEngine(provider()).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK,max_hops=10,max_transactions=1)
    assert len(r['transactions'])==1 and r['stats']['coverage']['partial']
    assert r['stats']['coverage']['observation_boundaries']['max_hops']==2
    assert r['stats']['coverage']['state']=='provider_limit'


@pytest.mark.asyncio
async def test_secret_never_in_errors_logs_or_settings_export(caplog):
    secret='fixture-do-not-expose'
    async def transport(m,p): raise RuntimeError('https://example.invalid/'+secret)
    p=AlchemyEthereumProvider(api_key=SecretStr(secret),transport=transport)
    r=await TraceEngine(p).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert secret not in json.dumps(r,default=str)+caplog.text
    config=Settings(ALCHEMY_API_KEY=secret,_env_file=None)
    assert secret not in repr(config)+config.model_dump_json()
    assert 'ALCHEMY_API_KEY' not in config.model_dump()


@pytest.mark.asyncio
async def test_no_demo_fallback_and_not_configured():
    p=get_provider('ethereum')
    assert isinstance(p,AlchemyEthereumProvider) and not p.is_demo
    r=await TraceEngine(p).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert not r['transactions'] and r['stats']['coverage']['state']=='not_configured'
    with pytest.raises(ValueError,match='explicit supported provider'):
        await TraceEngine(DemoProvider()).trace(ETH_ADDRESS,chain='ethereum')
    with pytest.raises(ValueError): get_provider('polygon')


async def ethereum_case(factory):
    ident=await _create_demo_case(factory)
    async with factory() as db:
        case=await db.get(Case,uuid.UUID(ident)); case.blockchain=Blockchain.ETHEREUM
        case.reported_wallet=RECIPIENT; case.is_demo=False
        await db.commit()
    return ident


@pytest.mark.asyncio
async def test_workflow_single_run_coverage_destination_and_failed_snapshot(investigation_session_factory, monkeypatch):
    monkeypatch.setattr(settings,'ALCHEMY_API_KEY',SecretStr('fixture-only'))
    ident=await ethereum_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        first=await InvestigationService(db,provider()).run_investigation(ident,direction='incoming',from_block=BLOCK,to_block=BLOCK)
        await db.commit()
        case=await db.get(Case,uuid.UUID(ident)); user=await db.get(User,case.investigator_id)
        cap=capability_for(case).model_dump(mode='json')
        assert cap['data_origin']=='observed' and cap['run_id']==first['run_id']
        assert cap['coverage']['run_id']==first['run_id']
        assert cap['destination']==first['destination']==(await destination_context(db,case))['selected']
        records=await get_transactions(ident,db=db,current_user=user)
        assert all(t['run_id']==first['run_id'] for t in records['transactions'])
        evidence=await get_evidence(ident,db=db,current_user=user)
        assert evidence['total'] and all(e['metadata']['run_id']==first['run_id'] for e in evidence['evidence'])
        assert await build_recommendations(db,case)
        readiness=await _case_context(db,case)
        assert not readiness['ready'] and readiness['run_id']==first['run_id']
        assert readiness['destination']==first['destination']
        report=await generate_report(ident,db=db,current_user=user)
        assert report['capability']['run_id']==first['run_id']
        assert first['run_id'] in str(report['sections'])
        await db.commit()
        async def failed(m,p): return 401, {}, None
        second=await InvestigationService(db,provider(failed)).run_investigation(ident,from_block=BLOCK,to_block=BLOCK)
        await db.commit()
        assert second['run_id']!=first['run_id'] and not second['snapshot_reused']
        assert not second['graph']['edges']
        assert capability_for(case).processing_state.value=='failed'
        assert not await build_recommendations(db,case)
        assert (await destination_context(db,case))['selected'] is None
        for fn in [get_transactions,get_evidence,get_report]:
            with pytest.raises(HTTPException) as exc: await fn(ident,db=db,current_user=user)
            assert exc.value.status_code==409
        assert (await _case_context(db,case))['destination'] is None
        third=await InvestigationService(db,provider()).run_investigation(ident,direction='incoming',from_block=BLOCK,to_block=BLOCK)
        await db.commit()
        assert third['run_id']!=first['run_id']
        assert (await get_evidence(ident,db=db,current_user=user))['total']==1
        with pytest.raises(HTTPException) as exc: await get_report(ident,db=db,current_user=user)
        assert exc.value.status_code==404


@pytest.mark.asyncio
async def test_api_uses_chain_factory_without_demo(investigation_session_factory,monkeypatch):
    ident=await ethereum_case(investigation_session_factory)
    import app.services.investigation_service as module
    selected=[]
    def factory(chain): selected.append(chain); return provider()
    monkeypatch.setattr(module,'get_provider',factory)
    async with investigation_session_factory() as db:
        case=await db.get(Case,uuid.UUID(ident)); user=await db.get(User,case.investigator_id)
        result=await investigate(ident,InvestigateRequest(from_block=BLOCK,to_block=BLOCK,direction='incoming'),db=db,current_user=user)
        assert selected==['ethereum'] and not result['is_demo']
        assert result['capability']['data_origin']=='observed'

@pytest.mark.asyncio
async def test_provider_failure_after_first_page_preserves_only_current_partial_records():
    t=CapturedTransport()
    original=next(e['result'] for e in t.entries if e['method']=='alchemy_getAssetTransfers' and e['params'][0].get('fromAddress')==ETH_ADDRESS)
    def override(m,p):
        if m=='alchemy_getAssetTransfers' and p[0].get('fromAddress')==ETH_ADDRESS:
            if p[0].get('pageKey'): return 401, {}, None
            return 200, {'result':{'transfers':[r for r in original['transfers'] if r['hash']==ETH_TX], 'pageKey':'next'}}, None
    t.override=override
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert len(r['transactions'])==1 and r['stats']['coverage']['partial']
    assert r['stats']['coverage']['state']=='invalid_credentials'


@pytest.mark.asyncio
async def test_pins_finalized_end_once_when_end_unspecified():
    t=CapturedTransport()
    t.override=lambda m,p: (200,{'result':{'number':hex(ETH_BLOCK)}},None) if m=='eth_getBlockByNumber' and p[0]=='finalized' else None
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK)
    assert r['stats']['coverage']['observation_boundaries']['to_block']==ETH_BLOCK
    assert sum(m=='eth_getBlockByNumber' and p[0]=='finalized' for m,p in t.calls)==1
    assert all(p[0]['toBlock']==hex(ETH_BLOCK) for m,p in t.calls if m=='alchemy_getAssetTransfers')


@pytest.mark.asyncio
async def test_uint256_one_wei_ignores_provider_floating_display_amount():
    t=CapturedTransport()
    tx=next(e['result'] for e in t.entries if e['method']=='eth_getTransactionByHash' and e['params']==[ETH_TX])
    tx['value']='0x1'
    for e in t.entries:
        if e['method']=='alchemy_getAssetTransfers':
            for item in e['result']['transfers']: item['value']=999999999.999
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert r['transactions'][0]['amount_base_units']=='1'
    assert r['transactions'][0]['amount_exact']=='0.000000000000000001'


@pytest.mark.asyncio
async def test_one_receipt_cannot_exceed_100_transfer_cap():
    t=CapturedTransport()
    rec=next(e['result'] for e in t.entries if e['method']=='eth_getTransactionReceipt' and e['params']==[ERC_TX])
    original=next(l for l in rec['logs'] if l['address']==MKR)
    rec['logs']=[dict(copy.deepcopy(original),logIndex=hex(n)) for n in range(101)]
    r=await TraceEngine(provider(t)).trace(RECIPIENT,chain='ethereum',direction='incoming',from_block=BLOCK,to_block=BLOCK,max_transactions=1000)
    assert len(r['transactions'])==100
    assert r['stats']['coverage']['state']=='provider_limit'
    assert r['stats']['coverage']['partial']


@pytest.mark.asyncio
async def test_200_request_hard_limit():
    p=provider()
    for _ in range(200): assert await p.rpc('eth_chainId',[])=='0x1'
    with pytest.raises(ProviderFailure,match='provider_limit'): await p.rpc('eth_chainId',[])
    assert p.requests==200


@pytest.mark.asyncio
async def test_conflicting_receipt_log_index_is_partial():
    t=CapturedTransport()
    rec=next(e['result'] for e in t.entries if e['method']=='eth_getTransactionReceipt' and e['params']==[ERC_TX])
    log=copy.deepcopy(next(l for l in rec['logs'] if l['address']==MKR))
    log['data']='0x'+format(1,'064x')
    rec['logs'].append(log)
    r=await TraceEngine(provider(t)).trace(RECIPIENT,chain='ethereum',direction='incoming',from_block=BLOCK,to_block=BLOCK)
    assert r['stats']['coverage']['partial']
    assert {'code':'conflicting_event'} in r['stats']['coverage']['provider_errors']
    assert len(r['transactions'])==1


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [None, [], {'transfers':None}, {'transfers':[], 'pageKey':42}])
async def test_malformed_transfer_response_is_never_empty_success(body):
    t=CapturedTransport(); t.override=lambda m,p:(200,{'result':body},None) if m=='alchemy_getAssetTransfers' else None
    r=await TraceEngine(provider(t)).trace(ETH_ADDRESS,chain='ethereum',from_block=ETH_BLOCK,to_block=ETH_BLOCK)
    assert not r['transactions'] and r['stats']['coverage']['state']=='unavailable'
    assert r['stats']['coverage']['partial']


@pytest.mark.asyncio
async def test_http_transport_auth_is_backend_only_and_redirects_disabled():
    calls=[]
    p=provider()
    class Response:
        status=200; headers={}
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def json(self,**kwargs): return {'jsonrpc':'2.0','id':p.requests,'result':'0x1'}
    class Session:
        def post(self,url,**kwargs): calls.append((url,kwargs)); return Response()
    p._transport=None; p._session=Session()
    assert await p.rpc('eth_chainId',[])=='0x1'
    endpoint, options=calls[0]
    assert endpoint.startswith('https://eth-mainnet.g.alchemy.com/v2/')
    assert endpoint.endswith('fixture-only') and options['allow_redirects'] is False
    assert 'fixture-only' not in json.dumps(options)


@pytest.mark.asyncio
async def test_unexpected_attempt_failure_cannot_restore_old_snapshot(investigation_session_factory,monkeypatch):
    ident=await ethereum_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        first=await InvestigationService(db,provider()).run_investigation(ident,direction='incoming',from_block=BLOCK,to_block=BLOCK)
        await db.commit()
        case=await db.get(Case,uuid.UUID(ident)); user=await db.get(User,case.investigator_id)
        async def fail(*args,**kwargs): raise RuntimeError('unexpected internal failure')
        monkeypatch.setattr(InvestigationService,'run_investigation',fail)
        with pytest.raises(HTTPException) as exc:
            await investigate(ident,InvestigateRequest(from_block=BLOCK,to_block=BLOCK),db=db,current_user=user)
        assert exc.value.status_code==500
        case=await db.get(Case,uuid.UUID(ident))
        cap=capability_for(case)
        assert cap.run_id!=first['run_id'] and cap.data_origin.value=='none'
        await db.refresh(user)
        with pytest.raises(HTTPException): await get_transactions(ident,db=db,current_user=user)
        assert not await build_recommendations(db,case)


@pytest.mark.asyncio
async def test_external_action_creation_remains_disabled(investigation_session_factory):
    from app.api.asset_actions import create_action_request
    ident=await ethereum_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        case=await db.get(Case,uuid.UUID(ident)); user=await db.get(User,case.investigator_id)
        with pytest.raises(HTTPException) as exc:
            await create_action_request(ident,None,None,db=db,current_user=user)
        assert exc.value.status_code==409

@pytest.mark.asyncio
async def test_two_hop_frontier_never_expands_third_hop():
    from app.providers.base import ProviderPage
    from app.core.transfers import normalize_transfer
    from datetime import datetime, timezone
    nodes=['0x'+str(n)*40 for n in range(1,5)]
    calls=[]
    class TraversalProvider(AlchemyEthereumProvider):
        async def prepare(self,start,end):
            self.start_block=start; self.end_block=end; self.pinned_hash='0x'+'f'*64
            self.requested_range={'from_block':start,'to_block':end}
        async def fetch_page(self,wallet,direction,continuation=None,limit=25):
            calls.append(wallet)
            index=nodes.index(wallet)
            event=normalize_transfer({'hash':'0x'+str(index+1)*64,'chain_id':'ethereum',
                'event_index':'native','asset_id':'ethereum:native','asset':'ETH',
                'from_address':wallet,'to_address':nodes[index+1], 'block_hash':self.pinned_hash,
                'amount_base_units':'1','token_decimals':18,'timestamp':datetime.now(timezone.utc)},'ethereum')
            return ProviderPage(records=[event],exhausted=True)
    r=await TraceEngine(TraversalProvider(api_key=SecretStr('fixture-only'),transport=CapturedTransport())).trace(nodes[0],chain='ethereum',from_block=1,to_block=1,max_hops=10)
    assert calls==nodes[:2] and len(r['transactions'])==2
    assert r['wallets'][nodes[2]]['expansion_state']=='hop_limit'
    assert r['stats']['coverage']['partial']


@pytest.mark.asyncio
async def test_whole_run_deadline_cancels_slow_transport():
    async def transport(m,p): await asyncio.sleep(60)
    p=provider(transport); p.timeout=0.02
    start=time.monotonic()
    async with p:
        with pytest.raises(ProviderFailure,match='timeout'): await p.rpc('eth_chainId',[])
    assert time.monotonic()-start < 1 and p.requests==1
