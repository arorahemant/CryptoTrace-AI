"""Startup/health isolation using the real lifespan and mocked upstream I/O."""
import asyncio
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

import app.main as main
from app.core.config import Settings, settings
from app.providers.alchemy import AlchemyEthereumProvider
from app.providers.demo import DemoProvider
from app.services import alchemy_diagnostic as service


SENTINEL = "startup-fixture-secret-never-expose"
SUMMARY_FIELDS = {"provider", "chain_id", "rpc_pass", "asset_transfer_pass", "error_code", "checked_at"}


@pytest.fixture
def startup(monkeypatch):
    # Exercise application startup without altering a real database or accounts.
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: True))
    session.__aenter__.return_value = session
    monkeypatch.setattr(main, "async_session_factory", lambda: session)
    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(main, "engine", SimpleNamespace(dialect=SimpleNamespace(name="sqlite"), dispose=AsyncMock()))
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "APP_ENV", "local")
    monkeypatch.setattr(settings, "SEED_DEMO_ACCOUNTS", False)
    monkeypatch.setattr(settings, "ALCHEMY_STARTUP_DIAGNOSTIC", True)
    monkeypatch.setattr(settings, "ALCHEMY_API_KEY", SecretStr(SENTINEL))
    monkeypatch.setattr(main.app.state, "alchemy_diagnostic", service.empty_startup_summary(False))
    calls = []

    async def send(provider, method, params):
        calls.append((method, params))
        value = "0x1" if method == "eth_chainId" else {"transfers": [{"private_data": SENTINEL}]}
        return 200, {"result": value}, None

    def no_demo(*args, **kwargs):
        pytest.fail("Startup diagnostic must never fall back to DemoProvider")

    monkeypatch.setattr(AlchemyEthereumProvider, "_send", send)
    monkeypatch.setattr(DemoProvider, "__init__", no_demo)
    return calls


async def completed_summary():
    async with asyncio.timeout(2):
        while main.app.state.alchemy_diagnostic["checked_at"] is None:
            await asyncio.sleep(0)
    return main.app.state.alchemy_diagnostic.copy()


async def assert_health(summary):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        for path in ("/health", "/api/v1/health", "/health"):
            response = await client.get(path)
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            assert response.json()["alchemy_diagnostic"] == summary
            assert set(response.json()["alchemy_diagnostic"]) == SUMMARY_FIELDS
            assert SENTINEL not in response.text


def test_startup_setting_defaults_off_and_accepts_environment(monkeypatch):
    monkeypatch.delenv("ALCHEMY_STARTUP_DIAGNOSTIC", raising=False)
    assert Settings(_env_file=None, DEMO_MODE=True, APP_ENV="local").ALCHEMY_STARTUP_DIAGNOSTIC is False
    monkeypatch.setenv("ALCHEMY_STARTUP_DIAGNOSTIC", "true")
    assert Settings(_env_file=None, DEMO_MODE=True, APP_ENV="local").ALCHEMY_STARTUP_DIAGNOSTIC is True


@pytest.mark.asyncio
async def test_disabled_startup_and_health_make_no_provider_calls(startup, monkeypatch):
    monkeypatch.setattr(settings, "ALCHEMY_STARTUP_DIAGNOSTIC", False)
    async with main.lifespan(main.app):
        await asyncio.sleep(0)
        await assert_health(service.empty_startup_summary(False))
    assert not startup


@pytest.mark.asyncio
async def test_one_startup_check_and_allowlisted_cached_health(startup, caplog):
    async with main.lifespan(main.app):
        summary = await completed_summary()
        assert summary == {"provider": "Alchemy", "chain_id": 1, "rpc_pass": True,
                           "asset_transfer_pass": True, "error_code": None, "checked_at": summary["checked_at"]}
        assert datetime.fromisoformat(summary["checked_at"]).tzinfo is not None
        await assert_health(summary)
        assert [method for method, _ in startup] == ["eth_chainId", "alchemy_getAssetTransfers"]
        query = startup[1][1][0]
        assert query["fromBlock"] == query["toBlock"] == "0x1"
        assert query["maxCount"] == "0x1"
        assert query["fromAddress"] == "0x000000000000000000000000000000000000dEaD"
        assert SENTINEL not in str(summary) + caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status,code", [(401, "invalid_credentials"), (429, "provider_limit"), (503, "unavailable")])
async def test_failure_is_cached_sanitized_and_does_not_change_health(startup, monkeypatch, caplog, status, code):
    async def fail(provider, method, params):
        startup.append(method)
        return status, {"error": {"message": SENTINEL}}, None

    monkeypatch.setattr(AlchemyEthereumProvider, "_send", fail)
    async with main.lifespan(main.app):
        summary = await completed_summary()
        assert not summary["rpc_pass"] and not summary["asset_transfer_pass"]
        assert summary["error_code"] == code
        await assert_health(summary)
        assert startup == ["eth_chainId", "alchemy_getAssetTransfers"]
        assert SENTINEL not in str(summary) + caplog.text


@pytest.mark.asyncio
async def test_missing_key_is_sanitized_without_demo_or_network(startup, monkeypatch):
    monkeypatch.setattr(settings, "ALCHEMY_API_KEY", None)
    async with main.lifespan(main.app):
        summary = await completed_summary()
        assert summary["error_code"] == "not_configured"
        assert not summary["rpc_pass"] and not summary["asset_transfer_pass"]
        await assert_health(summary)
        assert not startup


@pytest.mark.asyncio
async def test_partial_success_is_preserved(startup, monkeypatch):
    async def partial(provider, method, params):
        if method == "eth_chainId":
            return 200, {"result": "0x1"}, None
        return 200, {"result": {"transfers": None, "message": SENTINEL}}, None

    monkeypatch.setattr(AlchemyEthereumProvider, "_send", partial)
    async with main.lifespan(main.app):
        summary = await completed_summary()
        assert summary["rpc_pass"] and not summary["asset_transfer_pass"]
        assert summary["chain_id"] == 1 and summary["error_code"] == "malformed_response"
        await assert_health(summary)


@pytest.mark.asyncio
async def test_pending_check_does_not_block_startup_and_is_cancelled_on_shutdown(startup, monkeypatch):
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def stall():
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(service, "run_alchemy_diagnostic", stall)
    lifecycle = main.lifespan(main.app)
    await asyncio.wait_for(lifecycle.__aenter__(), 1)
    try:
        await asyncio.wait_for(entered.wait(), 1)
        await assert_health(service.empty_startup_summary(True))
    finally:
        await asyncio.wait_for(lifecycle.__aexit__(None, None, None), 1)
    assert cancelled.is_set()
    assert not startup


@pytest.mark.asyncio
async def test_startup_total_timeout_is_sanitized(startup, monkeypatch):
    async def stall():
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "run_alchemy_diagnostic", stall)
    monkeypatch.setattr(service, "STARTUP_TIMEOUT_SECONDS", 0.01)
    async with main.lifespan(main.app):
        summary = await completed_summary()
        assert summary["error_code"] == "timeout"
        assert not summary["rpc_pass"] and not summary["asset_transfer_pass"]
        await assert_health(summary)


@pytest.mark.asyncio
async def test_unexpected_setup_exception_cannot_leak_or_break_startup(startup, monkeypatch, caplog):
    async def fail():
        raise RuntimeError(SENTINEL)

    monkeypatch.setattr(service, "run_alchemy_diagnostic", fail)
    async with main.lifespan(main.app):
        summary = await completed_summary()
        assert summary["error_code"] == "unavailable"
        await assert_health(summary)
        assert SENTINEL not in str(summary) + caplog.text
