"""Exercise the real diagnostic route/auth/client with isolated upstream I/O."""
import asyncio
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import aiohttp
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.models import UserRole
from app.providers.alchemy import AlchemyEthereumProvider, ProviderFailure
from app.providers.demo import DemoProvider


PATH = "/api/v1/diagnostics/alchemy"
SENTINEL = "diagnostic-test-only-secret-must-not-appear"


@pytest.fixture
def diagnostic(monkeypatch):
    user = SimpleNamespace(id=uuid.uuid4(), role=UserRole.ADMIN,
                           is_active=True, is_demo_account=False,
                           username="diagnostic-admin", email="diagnostic-admin@example.com")
    db = SimpleNamespace(get=AsyncMock(return_value=user))

    async def get_test_db():
        yield db

    calls = []

    async def send(provider, method, params):
        calls.append((method, params))
        value = "0x1" if method == "eth_chainId" else {"transfers": []}
        return 200, {"result": value}, None

    def no_demo(*args, **kwargs):
        pytest.fail("Diagnostics must never instantiate DemoProvider")

    monkeypatch.setattr(settings, "ALCHEMY_API_KEY", SecretStr(SENTINEL))
    monkeypatch.setattr(AlchemyEthereumProvider, "_send", send)
    monkeypatch.setattr(DemoProvider, "__init__", no_demo)
    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = get_test_db
    # No lifespan: avoid migrations/seeding and use only the read-only auth stub.
    client = TestClient(app)
    token = create_access_token({"sub": str(user.id), "role": "admin"})
    try:
        yield client, {"Authorization": f"Bearer {token}"}, calls, user, db
    finally:
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_fixed_calls_and_sanitized_success(diagnostic, caplog):
    client, headers, calls, user, db = diagnostic
    response = client.get(PATH, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"provider": "Alchemy", "chain_id": 1,
                               "rpc_pass": True, "asset_transfer_pass": True, "errors": {}}
    assert calls == [("eth_chainId", []), ("alchemy_getAssetTransfers", [{
        "fromAddress": "0x000000000000000000000000000000000000dEaD",
        "fromBlock": "0x1", "toBlock": "0x1", "category": ["external"],
        "excludeZeroValue": True, "withMetadata": False, "maxCount": "0x1", "order": "asc",
    }])]
    db.get.assert_awaited_once()
    assert SENTINEL not in response.text + caplog.text


@pytest.mark.parametrize("identity", ["anonymous", "invalid", "reporter", "investigator",
                                      "supervisor", "disabled", "demo_admin", "unknown_user"])
def test_authorization_precedes_any_provider_call(diagnostic, identity):
    client, headers, calls, user, db = diagnostic
    expected = 403
    if identity == "anonymous":
        headers, expected = {}, 401
    elif identity == "invalid":
        headers, expected = {"Authorization": "Bearer invalid"}, 401
    elif identity == "reporter":
        headers = {"Authorization": "Bearer " + create_access_token({"sub": str(user.id), "role": "reporter"})}
    elif identity in {"investigator", "supervisor"}:
        # Even an admin claim cannot override the persisted account role.
        user.role = UserRole(identity)
    elif identity == "disabled":
        user.is_active = False
    elif identity == "demo_admin":
        user.is_demo_account = True
    else:
        db.get.return_value, expected = None, 401
    assert client.get(PATH, headers=headers).status_code == expected
    assert not calls


@pytest.mark.parametrize("status,code", [(401, "invalid_credentials"), (403, "invalid_credentials"),
                                        (429, "provider_limit"), (500, "unavailable")])
def test_upstream_errors_are_sanitized_without_retries(diagnostic, monkeypatch, caplog, status, code):
    client, headers, calls, _, _ = diagnostic

    async def fail(provider, method, params):
        calls.append(method)
        return status, {"error": {"message": SENTINEL}}, None

    monkeypatch.setattr(AlchemyEthereumProvider, "_send", fail)
    response = client.get(PATH, headers=headers)
    data = response.json()
    assert response.status_code == 200
    assert not data["rpc_pass"] and not data["asset_transfer_pass"]
    assert {e["error_type"] for e in data["errors"].values()} == {code}
    assert calls == ["eth_chainId", "alchemy_getAssetTransfers"]
    assert SENTINEL not in response.text + caplog.text


@pytest.mark.parametrize("failure,code", [(asyncio.TimeoutError(SENTINEL), "timeout"),
    (aiohttp.ClientConnectionError(SENTINEL), "unavailable"),
    (RuntimeError(SENTINEL), "unavailable"), (ProviderFailure(SENTINEL), "unavailable")])
def test_exception_text_never_leaks(diagnostic, monkeypatch, caplog, failure, code):
    client, headers, _, _, _ = diagnostic

    async def fail(*args):
        raise failure

    monkeypatch.setattr(AlchemyEthereumProvider, "_send", fail)
    response = client.get(PATH, headers=headers)
    assert not response.json()["rpc_pass"] and not response.json()["asset_transfer_pass"]
    assert {e["error_type"] for e in response.json()["errors"].values()} == {code}
    assert SENTINEL not in response.text + caplog.text


def test_missing_credentials_never_calls_upstream(diagnostic, monkeypatch):
    client, headers, calls, _, _ = diagnostic
    monkeypatch.setattr(settings, "ALCHEMY_API_KEY", None)
    data = client.get(PATH, headers=headers).json()
    assert not data["rpc_pass"] and not data["asset_transfer_pass"]
    assert {e["error_type"] for e in data["errors"].values()} == {"not_configured"}
    assert not calls


@pytest.mark.parametrize("chain,transfers,rpc_pass,asset_pass,error", [
    ("0x89", {"transfers": []}, False, True, "chain_mismatch"),
    ("invalid", {"transfers": []}, False, True, "malformed_response"),
    ("0x1", {"transfers": None}, True, False, "malformed_response"),
    ("0x1", [], True, False, "malformed_response"),
    ("0x1", {"transfers": [{"private_data": SENTINEL}]}, True, True, None),
])
def test_independent_checks_and_no_transfer_data_disclosure(
    diagnostic, monkeypatch, caplog, chain, transfers, rpc_pass, asset_pass, error,
):
    client, headers, _, _, _ = diagnostic

    async def send(provider, method, params):
        return 200, {"result": chain if method == "eth_chainId" else transfers}, None

    monkeypatch.setattr(AlchemyEthereumProvider, "_send", send)
    response = client.get(PATH, headers=headers)
    data = response.json()
    assert data["rpc_pass"] is rpc_pass and data["asset_transfer_pass"] is asset_pass
    assert {e["error_type"] for e in data["errors"].values()} == ({error} if error else set())
    assert SENTINEL not in response.text + caplog.text


def test_caller_cannot_select_rpc_or_wallet(diagnostic):
    client, headers, calls, _, _ = diagnostic
    response = client.get(PATH, headers=headers, params={"method": "eth_sendRawTransaction", "address": "other"})
    assert response.status_code == 200
    assert [method for method, _ in calls] == ["eth_chainId", "alchemy_getAssetTransfers"]
    assert calls[1][1][0]["fromAddress"] == "0x000000000000000000000000000000000000dEaD"
    calls.clear()
    assert client.post(PATH, headers=headers, json={"method": "eth_sendRawTransaction"}).status_code == 405
    assert not calls
