"""Event fidelity, exact accounting, bounded routes, and persisted consumers."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.transfers import normalize_transfer, asset_totals
from app.engines.trace_engine import TraceEngine
from app.engines.graph_engine import GraphEngine
from app.engines.pattern_engine import PatternEngine
from app.providers.demo import DemoProvider
from app.services.destination_service import classify_candidates, destination_context
from app.services.investigation_service import InvestigationService
from app.services.recommendation_service import build_recommendations
from app.services.ai_service import AIService
from app.api.asset_actions import _case_context
from app.api.cases import generate_report, get_findings, save_evidence
from app.schemas.schemas import EvidenceCreate
from app.models.models import Case, Transaction, User
from test_p0_remediation import investigation_session_factory, _create_demo_case, _counts


def transfer(source="A", target="B", tx_hash="tx1", event="0", units="1000000000000000001", asset="demo:native", decimals=18):
    return {"hash": tx_hash, "event_index": event, "chain_id": "demo", "asset_id": asset,
            "asset": "ETH" if asset == "demo:native" else "USDC", "token_decimals": decimals,
            "amount_base_units": units, "from_address": source, "to_address": target,
            "timestamp": datetime(2025, 8, 15, 10, 30, tzinfo=timezone.utc)}


class FixtureProvider(DemoProvider):
    def __init__(self, events, failing=None):
        self.events, self.failing = events, failing

    def get_all_demo_transactions(self):
        return self.events

    async def get_transactions(self, address, chain, direction="outgoing", limit=50, **kwargs):
        if address == self.failing:
            raise TimeoutError("fixture provider unavailable")
        return [dict(t) for t in self.events if t["from_address"] == address][:limit]


@pytest.mark.asyncio
async def test_repeated_transfers_and_multiple_events_in_one_transaction_are_preserved():
    events = [transfer(event="0"), transfer(event="1"), transfer(tx_hash="tx2")]
    result = await TraceEngine(FixtureProvider(events)).trace("A", min_amount=0)
    assert len(result["transactions"]) == 3
    assert len({t["transfer_id"] for t in result["transactions"]}) == 3
    graph = GraphEngine()
    graph.build_graph(result["transactions"], result["wallets"])
    edges = graph.serialize_for_frontend()["edges"]
    assert len(edges) == len({e["id"] for e in edges}) == 3
    assert all(e["amount_base_units"] == "1000000000000000001" for e in edges)
    assert result["wallets"]["B"]["received_by_asset"][0]["amount_base_units"] == "3000000000000000003"


def test_exact_uint256_amounts_and_chain_event_identity():
    tx = normalize_transfer(transfer(units=str(2**256 - 1)), "demo")
    assert tx["amount_base_units"] == str(2**256 - 1)
    tiny = normalize_transfer(transfer(units="1"), "demo")
    assert tiny["amount_exact"] == "0.000000000000000001"
    other = transfer()
    other.update(chain_id="ethereum", asset_id="ethereum:native")
    assert normalize_transfer(other, "ethereum")["transfer_id"] != normalize_transfer(transfer(), "demo")["transfer_id"]


@pytest.mark.parametrize("patch", [
    {"amount_base_units": 1.5}, {"amount_base_units": "-1"},
    {"amount_base_units": str(2**256)}, {"token_decimals": -1},
    {"token_decimals": True}, {"event_index": None}, {"chain_id": "ethereum"},
    {"asset_id": "USDC"},
])
def test_invalid_canonical_records_fail_closed(patch):
    with pytest.raises(ValueError):
        normalize_transfer({**transfer(), **patch}, "demo")


@pytest.mark.asyncio
async def test_mixed_assets_are_never_summed_or_compared_as_one_currency():
    events = [transfer(), transfer(event="1", asset="demo:token:usdc", decimals=6, units="99000001")]
    result = await TraceEngine(FixtureProvider(events)).trace("A", min_amount=0)
    totals = result["stats"]["transfer_volume_by_asset"]
    assert {t["asset_id"]: t["amount_exact"] for t in totals} == {
        "demo:native": "1.000000000000000001", "demo:token:usdc": "99.000001"}
    assert result["stats"]["total_amount_traced"] is None
    findings = PatternEngine().detect_all(result["transactions"], result["wallets"], result["paths"])
    repeated = next(f for f in findings if f["pattern_type"] == "repeated_connections")
    assert "99.000001 USDC" in repeated["description"]
    assert len(repeated["metadata"]["transfer_volume_by_asset"]) == 2


@pytest.mark.asyncio
async def test_cycles_bounds_and_endpoint_reasons():
    events = [transfer(), transfer("B", "A", "tx2"), transfer("B", "C", "tx3")]
    complete = await TraceEngine(FixtureProvider(events)).trace("A", min_amount=0)
    assert len(complete["transactions"]) == 3
    assert complete["wallets"]["C"]["endpoint_kind"] == "last_observed_wallet"
    bounded = await TraceEngine(FixtureProvider(events)).trace("A", max_hops=1, min_amount=0)
    assert bounded["wallets"]["B"]["expansion_state"] == "hop_limit"
    assert not bounded["wallets"]["B"]["is_destination"]
    assert bounded["stats"]["trace_status"] == "partial"
    failed = await TraceEngine(FixtureProvider(events, failing="B")).trace("A", min_amount=0)
    assert failed["wallets"]["B"]["expansion_state"] == "provider_error"
    limited = await TraceEngine(FixtureProvider(events)).trace("A", max_transactions=1, min_amount=0)
    assert len(limited["transactions"]) == 1
    assert limited["stats"]["trace_status"] == "partial"


@pytest.mark.asyncio
async def test_provider_cap_conflicting_events_and_decimals_are_partial():
    events = [transfer(tx_hash=f"tx{i}") for i in range(51)]
    result = await TraceEngine(FixtureProvider(events)).trace("A", min_amount=0)
    assert len(result["transactions"]) == 50
    assert result["wallets"]["A"]["expansion_state"] == "provider_limit"
    conflict = await TraceEngine(FixtureProvider([transfer(), transfer(units="2")])).trace("A", min_amount=0)
    assert conflict["stats"]["malformed_transactions"] == 1
    assert len(conflict["transactions"]) == 1
    conflict = await TraceEngine(FixtureProvider([transfer(), transfer(event="1", decimals=6)])).trace("A", min_amount=0)
    assert conflict["stats"]["malformed_transactions"] == 1


def test_candidate_classification_and_bounded_path_do_not_reward_longer_value_sum():
    wallets = {a: {"hop_distance": i, "expansion_state": "expanded", "endpoint_kind": "intermediary"}
               for i, a in enumerate(["A", "B", "C", "D"])}
    wallets["A"]["is_reported"] = True
    wallets["D"]["endpoint_kind"] = "last_observed_wallet"
    candidates = classify_candidates(wallets, {"D": {"attribution_status": "likely_inferred"}})
    assert candidates[0]["kind"] == "candidate_vasp"
    assert classify_candidates(wallets, {"D": {"attribution_status": "known_verified"}})[0]["kind"] == "identified_service_address"
    events = [transfer("A", "D", "direct", units="1"), transfer("A", "B"),
              transfer("B", "C", "bc"), transfer("C", "D", "cd"), transfer("C", "A", "cycle")]
    graph = GraphEngine()
    graph.build_graph([normalize_transfer(t, "demo") for t in events], wallets)
    assert graph.get_primary_path("A", "D") == ["A", "D"]
    assert graph.get_primary_path("A", "C", max_hops=1) == ["A"]


@pytest.mark.asyncio
async def test_demo_persistence_replay_shared_destination_reports_and_run_identity(investigation_session_factory):
    case_id = await _create_demo_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        service = InvestigationService(db)
        first = await service.run_investigation(case_id)
        await db.commit()
        assert await _counts(db, case_id) == (9, 10, 9, 12, 10, 10, 9, 1)
        reused = await service.run_investigation(case_id)
        assert reused["run_id"] == first["run_id"]
        assert reused["snapshot_reused"] and not first["snapshot_reused"]
        case = await db.get(Case, uuid.UUID(case_id))
        user = await db.get(User, case.investigator_id)
        graph = await service.get_graph_data(case_id)
        replay = await service.get_replay_events(case_id)
        assert {e["transfer_id"] for e in replay} == {e["id"] for e in graph["edges"]}
        assert all(e["cumulative_amount"] is None for e in replay)
        assert all(e["amount_exact"] for e in graph["edges"])
        context = await _case_context(db, case)
        findings = await get_findings(case_id, db, user)
        recommendations = await build_recommendations(db, case)
        report = await generate_report(case_id, db, None, user)
        ai = await AIService(db)._build_context(case.id)
        selected = graph["destination"]
        assert selected["address"] == "0xExchang009"
        assert selected == first["destination"] == context["destination"] == findings["destination"] == ai["destination"]
        assert selected["kind"] == "candidate_vasp"
        assert all(r["target_wallet"] == selected["address"] for r in recommendations if r["type"] in {"review_destination_attribution", "prepare_asset_action_request"})
        assert any(selected["address"] in section["content"] and first["run_id"] in section["content"] for section in report["sections"])


@pytest.mark.asyncio
async def test_multiple_event_roundtrip_and_evidence_requires_event_selection(investigation_session_factory):
    from fastapi import HTTPException
    case_id = await _create_demo_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        events = [transfer("0xReported001", event="0"), transfer("0xReported001", event="1", units="1")]
        service = InvestigationService(db, FixtureProvider(events))
        first = await service.run_investigation(case_id, min_amount=0)
        await db.commit()
        reused = await service.run_investigation(case_id)
        assert len(reused["graph"]["edges"]) == 2
        assert {e["amount_base_units"] for e in reused["graph"]["edges"]} == {"1", "1000000000000000001"}
        case = await db.get(Case, uuid.UUID(case_id))
        user = await db.get(User, case.investigator_id)
        request = EvidenceCreate(title="Transfer selection", description="Select exact transfer event", transaction_hash="tx1")
        with pytest.raises(HTTPException) as exc:
            await save_evidence(case_id, request, db, None, user)
        assert exc.value.status_code == 422
        request.transfer_id = first["graph"]["edges"][1]["transfer_id"]
        saved = await save_evidence(case_id, request, db, None, user)
        assert saved["transfer_id"] == request.transfer_id


@pytest.mark.asyncio
async def test_legacy_event_can_be_bookmarked_without_inventing_precision(investigation_session_factory):
    case_id = await _create_demo_case(investigation_session_factory)
    async with investigation_session_factory() as db:
        await InvestigationService(db).run_investigation(case_id)
        case = await db.get(Case, uuid.UUID(case_id))
        user = await db.get(User, case.investigator_id)
        tx = (await db.scalars(select(Transaction).where(Transaction.case_id == case.id))).first()
        tx.metadata_, tx.transfer_id = None, None
        await db.flush()
        request = EvidenceCreate(title="Legacy transfer bookmark", description="Preserve existing legacy evidence",
                                 transaction_hash=tx.hash, transfer_id=f"legacy:{tx.id}")
        saved = await save_evidence(case_id, request, db, None, user)
        assert saved["transfer_id"] == f"legacy:{tx.id}"


def test_uninvestigated_case_does_not_claim_a_run_identity():
    from app.core.capabilities import capability_for
    from app.models.models import Blockchain, CaseStatus
    case = Case(id=uuid.uuid4(), blockchain=Blockchain.DEMO, status=CaseStatus.NEW)
    assert capability_for(case).run_id is None
