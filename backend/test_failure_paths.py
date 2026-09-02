"""Unit-level failure and boundary checks for the investigation engines."""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import httpx
from sqlalchemy.exc import OperationalError

from app.api.auth import _check_login_rate_limit, _failed_logins, _record_failed_login
from app.api.cases import _generate_case_number
from app.core.database import get_db
from app.engines.pattern_engine import PatternEngine
from app.engines.risk_engine import RiskEngine
from app.engines.trace_engine import TraceEngine
from app.main import app
from app.providers.base import BlockchainProvider
from app.providers.demo import DemoProvider
from app.services.ai_service import AIService


class UnavailableProvider(BlockchainProvider):
    @property
    def provider_name(self) -> str:
        return "unavailable"

    @property
    def is_demo(self) -> bool:
        return False

    async def validate_address(self, address: str, chain: str) -> bool:
        return False

    async def get_network(self, address: str):
        return None

    async def get_transactions(self, address: str, chain: str, **kwargs):
        raise TimeoutError("provider timeout")

    async def get_transaction(self, tx_hash: str, chain: str):
        return None

    async def get_balance(self, address: str, chain: str) -> float:
        return 0.0


class MalformedProvider(UnavailableProvider):
    @property
    def provider_name(self) -> str:
        return "malformed"

    async def get_transactions(self, address: str, chain: str, **kwargs):
        return [
            None,
            {
                "hash": "bad-amount",
                "from_address": "0xA",
                "to_address": "0xB",
                "amount": "not-a-number",
                "timestamp": datetime.now(timezone.utc),
            },
        ]


def _tx(tx_hash: str, source: str, destination: str, minute: int = 0) -> dict:
    return {
        "hash": tx_hash,
        "from_address": source,
        "to_address": destination,
        "amount": 1.0,
        "asset": "ETH",
        "timestamp": datetime(2025, 8, 15, 10, minute, tzinfo=timezone.utc),
    }


@pytest.mark.asyncio
async def test_provider_timeout_returns_no_fabricated_transactions():
    result = await TraceEngine(UnavailableProvider()).trace(
        "0xReported001", max_hops=2, time_window_hours=24
    )

    assert result["transactions"] == []
    assert result["stats"]["provider_errors"] == 1
    assert result["stats"]["malformed_transactions"] == 0
    assert result["stats"]["trace_status"] == "partial"
    assert result["stats"]["trace_warning"]
    assert list(result["wallets"]) == ["0xReported001"]


@pytest.mark.asyncio
async def test_malformed_provider_records_are_skipped_safely():
    result = await TraceEngine(MalformedProvider()).trace(
        "0xReported001", max_hops=2, time_window_hours=24
    )

    assert result["transactions"] == []
    assert result["stats"]["provider_errors"] == 0
    assert result["stats"]["malformed_transactions"] == 2
    assert result["stats"]["trace_status"] == "partial"
    assert result["stats"]["trace_warning"]


@pytest.mark.asyncio
async def test_unknown_demo_wallet_returns_empty_investigation_data():
    result = await TraceEngine(DemoProvider()).trace(
        "0xUnknownWallet", max_hops=5, time_window_hours=720
    )

    assert result["transactions"] == []
    assert result["stats"]["total_transactions"] == 0
    assert result["stats"]["total_wallets"] == 1
    assert result["stats"]["trace_status"] == "complete"
    assert result["stats"]["trace_warning"] is None


def test_patterns_and_risk_remain_deterministic_and_explainable():
    transactions = [
        _tx("tx-1", "0xReported001", "0xIntermed002", 0),
        _tx("tx-2", "0xIntermed002", "0xSplit001", 1),
        _tx("tx-3", "0xIntermed002", "0xSplit002", 2),
        _tx("tx-4", "0xIntermed002", "0xSplit003", 3),
    ]
    wallets = {
        address: {"hop_distance": index}
        for index, address in enumerate(
            ["0xReported001", "0xIntermed002", "0xSplit001", "0xSplit002", "0xSplit003"]
        )
    }
    findings = PatternEngine(split_threshold=3).detect_all(
        transactions, wallets, [["0xReported001", "0xIntermed002", "0xSplit001"]]
    )

    finding_types = {finding["pattern_type"] for finding in findings}
    assert "fund_splitting" in finding_types
    assert "rapid_movement" in finding_types

    risk = RiskEngine().assess_wallet_risk(
        "0xIntermed002",
        findings,
        {"hop_distance": 1},
        intermediary_data={"centrality": 0.5},
    )
    assert risk["risk_score"] > 0
    assert risk["risk_category"] in {"medium", "high", "critical"}
    assert risk["contributing_signals"]
    assert "criminal" not in risk["explanation"].lower()


@pytest.mark.asyncio
async def test_ai_provider_timeout_falls_back_to_case_data(monkeypatch):
    import openai

    class BrokenCompletions:
        async def create(self, **kwargs):
            raise TimeoutError("AI provider timeout")

    class BrokenClient:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=BrokenCompletions())

    monkeypatch.setattr(openai, "AsyncOpenAI", BrokenClient)
    context = {
        "case": {"case_number": "CT-TEST", "title": "Failure test", "is_demo": True},
        "wallets": [],
        "transactions_count": 0,
        "findings": [],
        "evidence_count": 0,
        "risk_assessments": [],
        "vasp_attributions": [],
        "fund_flow_path": [],
    }

    result = await AIService(None)._query_llm("Summarize the investigation", context)

    assert result["grounded"] is True
    assert "Investigation Summary" in result["answer"]
    assert result["sources"]


def test_missing_attribution_does_not_create_attribution_signal():
    risk = RiskEngine().assess_wallet_risk(
        "0xUnknown",
        [],
        {"hop_distance": 3},
        vasp_data=None,
    )

    assert risk["risk_category"] == "low"
    assert all(
        signal["signal_name"] != "Attributed Destination"
        for signal in risk["contributing_signals"]
    )


def test_login_rate_limit_returns_retryable_429():
    key = "failure-test-client"
    _failed_logins.pop(key, None)
    try:
        for _ in range(5):
            _record_failed_login(key)
        with pytest.raises(Exception) as raised:
            _check_login_rate_limit(key)
        assert raised.value.status_code == 429
        assert raised.value.headers["Retry-After"] == "60"
    finally:
        _failed_logins.pop(key, None)


def test_case_number_has_collision_resistant_suffix():
    case_number = _generate_case_number()
    assert case_number.startswith("CT-")
    assert len(case_number.rsplit("-", 1)[1]) == 8


@pytest.mark.asyncio
async def test_database_unavailable_returns_safe_retryable_response():
    async def broken_db():
        raise OperationalError("database unavailable", None, RuntimeError("connection refused"))
        yield  # pragma: no cover - keeps this an async-generator dependency

    app.dependency_overrides[get_db] = broken_db
    try:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/cases")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "5"
    assert response.json() == {"detail": "Database temporarily unavailable. Please retry."}
