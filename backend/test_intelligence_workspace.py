"""Case-scoped intelligence: real captured observations, local explanations, no lookups."""
import uuid
from types import SimpleNamespace
from datetime import datetime, timezone

import pytest
from pydantic import SecretStr
from sqlalchemy import select

from app.core.config import settings
from app.models.models import Case, Blockchain, User, Evidence, VASPAttribution
from app.services.attribution_service import AttributionScope, StoredAttributionSource, normalize_attribution
from app.services.destination_service import destination_context
from app.services.investigation_service import InvestigationService
from app.services.ai_service import AIService
from app.services.recommendation_service import build_recommendations
from app.api.asset_actions import _case_context
from app.api.cases import get_findings, generate_report
from app.providers.alchemy import AlchemyEthereumProvider
from test_p0_remediation import investigation_session_factory, _create_demo_case
from test_high_activity import Replay, ADDRESS, START, END


@pytest.mark.asyncio
@pytest.mark.parametrize('status,provenance,expected', [
    ('known_verified', 'institutional_source', 'known_verified'),
    ('likely_inferred', 'analytical_inference', 'likely_inferred'),
    ('unknown', 'unknown', 'unknown'),
    ('known_verified', 'demo_intelligence', 'unknown'),
    ('likely_inferred', 'unknown', 'unknown'),
])
async def test_attribution_source_semantics_and_network_isolation(status, provenance, expected):
    scope = AttributionScope('ethereum', 'run', frozenset({'address'}), {'address': {'tx'}}, {'address': {'evidence'}})
    row = SimpleNamespace(wallet_address='address', entity_name='Test-only institutional label',
        attribution_status=status, provenance=provenance, source_reference='test-record',
        verified_at=datetime(2024, 1, 1, tzinfo=timezone.utc), supporting_transaction_hashes=['tx'],
        supporting_evidence_ids=['evidence', 'foreign-evidence'])
    data = (await StoredAttributionSource([row]).lookup(scope))['address']
    assert data['attribution_status'] == expected
    assert 'foreign-evidence' not in data['supporting_evidence_ids']
    if expected == 'unknown':
        assert data['entity_name'] is None
    row.supporting_transaction_hashes = ['foreign-tx']
    row.supporting_evidence_ids = ['foreign-evidence']
    unsupported = (await StoredAttributionSource([row]).lookup(scope))['address']
    assert unsupported['attribution_status'] == 'unknown' and unsupported['entity_name'] is None


@pytest.mark.parametrize('malformed', [[], {'label': 'untrusted'}, 42, None])
def test_untrusted_attribution_metadata_cannot_create_verified_identity(malformed):
    result = normalize_attribution({'entity_name': malformed, 'attribution_status': 'known_verified',
        'provenance': 'trusted_external_source', 'verified_at': 'invalid-timestamp',
        'supporting_evidence_ids': {'not': 'a-list'}, 'source_reference': malformed})
    assert result['attribution_status'] == 'unknown'
    assert result['entity_name'] is None


@pytest.mark.asyncio
async def test_high_activity_shared_intelligence_copilot_report_and_no_invented_facts(investigation_session_factory, monkeypatch):
    monkeypatch.setattr(settings, 'ALCHEMY_API_KEY', SecretStr('fixture-only'))
    ident = await _create_demo_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        case = await db.get(Case, uuid.UUID(ident))
        case.blockchain, case.reported_wallet, case.is_demo = Blockchain.ETHEREUM, ADDRESS, False
        provider = AlchemyEthereumProvider(transport=Replay(), api_key=SecretStr('fixture-only'))
        service = InvestigationService(db, provider)
        run = await service.run_investigation(ident, from_block=START, to_block=END)
        await db.commit()
        user = await db.get(User, case.investigator_id)
        graph = await service.get_graph_data(ident)
        intel = graph['destination_intelligence']
        selection = await destination_context(db, case)
        readiness = await _case_context(db, case)
        findings = await get_findings(ident, db, user)
        recommendations = await build_recommendations(db, case)
        copilot = await AIService(db).query(ident, 'Show supporting transfers and evidence')
        report = await generate_report(ident, db, None, user)
        assert len(graph['edges']) == len(graph['nodes']) == 62
        assert intel['candidate'] == selection['selected'] == graph['destination'] == copilot['destination'] == readiness['destination'] == findings['destination']
        assert all(r['target_wallet'] == intel['candidate']['address'] for r in recommendations)
        assert intel['run_id'] == copilot['run_id'] == run['run_id']
        assert copilot['coverage']['partial'] and copilot['data_origin'] == 'observed'
        assert len([r for r in copilot['supporting_records'] if r['kind'] == 'transfer']) == 62
        assert len([r for r in copilot['supporting_records'] if r['kind'] == 'evidence']) == 62
        assert {r['id'] for r in copilot['supporting_records'] if r['kind'] == 'transfer'} == {e['id'] for e in graph['edges']}
        assert intel['attribution']['attribution_status'] == 'unknown'
        assert intel['attribution']['entity_name'] is None
        assert intel['external_attribution_provider'] == 'not_connected'
        assert intel['freshness'] == 'unknown' and intel['verified_at'] is None
        assert not findings['findings'] and not readiness['ready']
        assert report['sections'][-2]['metadata']['destination_intelligence'] == intel
        assert any(check['label'] == 'Evidence preserved' for check in readiness['checks'])
        unknown = await AIService(db).query(ident, 'Why is attribution UNKNOWN?')
        assert 'Attribution: UNKNOWN' in unknown['answer']
        flag = await AIService(db).query(ident, 'Why was this wallet flagged?', wallet_address=ADDRESS)
        assert 'no recorded finding' in flag['answer'] and not flag['supporting_records']
        outside = await AIService(db).query(ident, 'Show supporting transfers', wallet_address='outside-this-case')
        assert 'NOT AVAILABLE' in outside['answer'] and not outside['supporting_records']
        assert provider.requests == 29  # No Copilot/report provider requests.
        risk = await AIService(db).query(ident, 'Explain the risk score')
        assert 'NOT AVAILABLE' in risk['answer'] and not risk['supporting_records']


@pytest.mark.asyncio
async def test_demo_evidence_chain_and_verified_record_are_preserved(investigation_session_factory):
    ident = await _create_demo_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        service = InvestigationService(db)
        await service.run_investigation(ident)
        case = await db.get(Case, uuid.UUID(ident))
        first = await service.get_graph_data(ident)
        intel = first['destination_intelligence']
        assert len(first['nodes']) == 9 and len(first['edges']) == 10
        assert intel['data_origin'] == 'demo' and intel['attribution']['attribution_status'] == 'likely_inferred'
        assert intel['findings'] and intel['evidence']
        for question in ('Which wallets are intermediaries?', 'Explain the risk assessments'):
            response = await AIService(db).query(ident, question)
            assert response['supporting_records']
            assert {r['id'] for r in response['supporting_records']} <= {n['address'] for n in first['nodes']}
        evidence_ids = {e['id'] for e in intel['evidence']}
        for f in intel['findings']:
            assert set(f['evidence_ids']) <= evidence_ids
            assert set(f['transfer_ids']) <= {t['id'] for t in intel['supporting_transfers']}
        destination_hashes = {t['hash'] for t in intel['supporting_transfers'] if t['target'] == intel['candidate']['address']}
        db.add(VASPAttribution(case_id=case.id, wallet_address=intel['candidate']['address'],
            entity_name='Test-only verified source', attribution_type='verified', confidence='known',
            attribution_status='known_verified', provenance='institutional_source', source='test_institution',
            source_reference='test-record', verified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            supporting_transaction_hashes=[next(iter(destination_hashes))], supporting_evidence_ids=[]))
        await db.flush()
        graph = await service.get_graph_data(ident)
        verified = graph['destination_intelligence']
        assert verified['attribution']['attribution_status'] == 'known_verified'
        assert verified['verified_at'] and verified['freshness'] == 'verification_recorded_not_revalidated'
        response = await AIService(db).query(ident, 'Why this destination?')
        assert 'Attribution: VERIFIED' in response['answer'] and response['data_origin'] == 'demo'
        assert (await _case_context(db, case))['attribution_status'] == 'known_verified'
        user = await db.get(User, case.investigator_id)
        report = await generate_report(ident, db, None, user)
        persisted = report['sections'][-2]['metadata']['destination_intelligence']
        assert isinstance(persisted['attribution']['verified_at'], str)
        assert persisted['attribution']['attribution_status'] == 'known_verified'


@pytest.mark.asyncio
async def test_no_external_llm_even_when_credentials_configured(monkeypatch):
    import openai
    def forbidden(**kwargs):
        raise AssertionError('External model must not receive case data')
    monkeypatch.setattr(openai, 'AsyncOpenAI', forbidden)
    response = await AIService(None)._query_llm('Summarize the investigation', {'case': {'is_demo': True}})
    assert response['grounded'] and 'UNKNOWN' in response['answer']


@pytest.mark.asyncio
async def test_unavailable_case_has_no_prior_destination_or_evidence(investigation_session_factory):
    ident = await _create_demo_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        case = await db.get(Case, uuid.UUID(ident))
        case.blockchain, case.is_demo = Blockchain.ETHEREUM, False
        response = await AIService(db).query(ident, 'Why this destination?')
        assert not response['sources'] and 'unavailable' in response['answer']
        assert (await destination_context(db, case))['selected'] is None
