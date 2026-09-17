"""First-admin boundaries using disposable databases and synthetic secrets only."""
import asyncio
import logging
from pathlib import Path
import runpy
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import SecretStr, ValidationError
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.api import admin_bootstrap as api
from app.api.auth import router as auth_router, _failed_logins
from app.core import admin_bootstrap as service
from app.core.config import Settings, settings
from app.core.database import Base, get_db
from app.core.permissions import permissions_for
from app.core.security import get_password_hash, verify_password
from app.models.models import AuditLog, FirstAdminBootstrapState, ReporterAccount, User, UserRole
from app.schemas.schemas import FirstAdminBootstrapRequest

PATH = "/api/v1/auth/bootstrap-first-admin"
TOKEN = "synthetic-bootstrap-token-0123456789abcdef"
PASSWORD = "synthetic-admin-password-9012"
BODY = {"username": "real-operator", "email": "operator@example.com",
        "full_name": "Production Operator", "password": PASSWORD}


@pytest_asyncio.fixture
async def harness(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'bootstrap.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as db:
        db.add(FirstAdminBootstrapState(id=1))
    monkeypatch.setattr(settings, "FIRST_ADMIN_BOOTSTRAP_TOKEN", SecretStr(TOKEN))
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "SEED_DEMO_ACCOUNTS", False)
    _failed_logins.clear()
    app = FastAPI()
    app.include_router(api.router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")

    async def session():
        async with factory() as db:
            try:
                yield db
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    app.dependency_overrides[get_db] = session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        yield SimpleNamespace(client=client, factory=factory, engine=engine)
    _failed_logins.clear()
    await engine.dispose()


async def post(harness, body=None, token=TOKEN):
    headers = {api.HEADER: token} if token is not None else {}
    return await harness.client.post(PATH, json=BODY if body is None else body, headers=headers)


async def counts(harness):
    async with harness.factory() as db:
        return tuple([await db.scalar(select(func.count()).select_from(model)) for model in (User, AuditLog)])


async def add_user(harness, *, demo=False, active=True, role=UserRole.ADMIN, **fields):
    values = dict(username="existing", email="existing@example.com", full_name="Existing Operator",
                  hashed_password=get_password_hash(PASSWORD), role=role, is_active=active, is_demo_account=demo)
    values.update(fields)
    async with harness.factory.begin() as db:
        db.add(User(**values))


def test_disabled_default_and_secret_serialization(monkeypatch):
    monkeypatch.delenv("FIRST_ADMIN_BOOTSTRAP_TOKEN", raising=False)
    assert Settings(_env_file=None).FIRST_ADMIN_BOOTSTRAP_TOKEN is None
    configured = Settings(FIRST_ADMIN_BOOTSTRAP_TOKEN=TOKEN, _env_file=None)
    assert TOKEN not in repr(configured)
    assert "FIRST_ADMIN_BOOTSTRAP_TOKEN" not in configured.model_dump()
    assert PASSWORD not in repr(FirstAdminBootstrapRequest(**BODY))


def test_startup_validation_does_not_echo_bootstrap_secret():
    with pytest.raises(ValidationError) as error:
        Settings(APP_ENV="invalid", FIRST_ADMIN_BOOTSTRAP_TOKEN=TOKEN, _env_file=None)
    assert TOKEN not in str(error.value)


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, "", "short", "x" * 129, " " * 40])
async def test_disabled_or_misconfigured(harness, monkeypatch, token):
    monkeypatch.setattr(settings, "FIRST_ADMIN_BOOTSTRAP_TOKEN", SecretStr(token) if token is not None else None)
    response = await post(harness)
    assert response.status_code == 404
    assert await counts(harness) == (0, 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("token", [None, "invalid-synthetic-token", "x" * 129])
async def test_invalid_token(harness, token):
    response = await post(harness, token=token)
    assert response.status_code == 403
    assert await counts(harness) == (0, 0)


@pytest.mark.asyncio
async def test_success_hash_permissions_audit_and_reuse(harness, caplog):
    caplog.set_level(logging.INFO)
    response = await post(harness)
    assert response.status_code == 201
    assert response.json() == {"detail": "Administrator provisioned"}
    assert response.headers["cache-control"] == "no-store"
    async with harness.factory() as db:
        user = await db.scalar(select(User))
        assert user.role == UserRole.ADMIN and user.is_active and not user.is_demo_account
        assert "users.manage" in permissions_for(user)
        assert user.hashed_password != PASSWORD
        assert verify_password(PASSWORD, user.hashed_password)
        event = await db.scalar(select(AuditLog))
        assert event.action == "operator_admin_bootstrapped"
        assert event.user_id == user.id and event.resource_id == str(user.id)
        assert event.details is None
        assert (await db.get(FirstAdminBootstrapState, 1)).consumed
    assert (await post(harness)).status_code == 409
    assert await counts(harness) == (1, 1)
    assert TOKEN not in response.text + caplog.text
    assert PASSWORD not in response.text + caplog.text
    assert "access_token" not in response.text


@pytest.mark.asyncio
@pytest.mark.parametrize("active", [True, False])
async def test_existing_non_demo_admin_including_disabled(harness, active):
    await add_user(harness, active=active)
    assert (await post(harness)).status_code == 409
    assert await counts(harness) == (1, 0)
    async with harness.factory.begin() as db:
        await db.execute(delete(User))
    assert (await post(harness)).status_code == 409


@pytest.mark.asyncio
async def test_demo_admin_does_not_block(harness):
    await add_user(harness, demo=True, username="admin", email="admin@cryptotrace.ai")
    assert (await post(harness)).status_code == 201
    assert await counts(harness) == (2, 1)
    response = await harness.client.post("/api/v1/auth/login", json={"username": "admin", "password": PASSWORD})
    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("model", [User, ReporterAccount])
@pytest.mark.parametrize("field", ["username", "email"])
async def test_duplicate_identity(harness, model, field):
    values = dict(username="duplicate", email="duplicate@example.com", full_name="Duplicate Identity",
                  hashed_password="unused", is_demo_account=False)
    values[field] = BODY[field]
    async with harness.factory.begin() as db:
        db.add(model(**values))
    assert (await post(harness)).status_code == 409
    async with harness.factory() as db:
        assert not (await db.get(FirstAdminBootstrapState, 1)).consumed
        assert await db.scalar(select(func.count()).select_from(AuditLog)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [
    {"password": "short"}, {"password": "x" * 73}, {"password": "\u00e9" * 37},
    {"role": "admin"}, {"role": "investigator"}, {"email": "bad-email"},
    {"username": "bad username"}, {"full_name": "   "},
    {"username": "admin", "email": "admin@cryptotrace.ai"},
])
async def test_invalid_body_never_echoes_inputs(harness, overrides, caplog):
    body = {**BODY, **overrides}
    response = await post(harness, body=body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid bootstrap request"}
    assert body["password"] not in response.text + caplog.text
    assert TOKEN not in response.text + caplog.text
    assert await counts(harness) == (0, 0)


@pytest.mark.asyncio
async def test_malformed_missing_oversized_and_duplicate_header(harness):
    for body in (b'{"password":"secret-sentinel"', b"x" * 8193, b"{}"):
        response = await harness.client.post(PATH, content=body, headers={api.HEADER: TOKEN})
        assert response.status_code == 422
        assert "secret-sentinel" not in response.text
    response = await harness.client.post(PATH, json=BODY, headers=[(api.HEADER, TOKEN), (api.HEADER, TOKEN)])
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_attempt_limit_persists_across_clients_and_token_rotation(harness, monkeypatch):
    for _ in range(api.ATTEMPT_LIMIT):
        assert (await post(harness, token="bad")).status_code == 403
    rotated = "rotated-synthetic-bootstrap-token-0123456789"
    monkeypatch.setattr(settings, "FIRST_ADMIN_BOOTSTRAP_TOKEN", SecretStr(rotated))
    assert (await post(harness, token=rotated)).status_code == 429
    async with harness.factory.begin() as db:
        state = await db.get(FirstAdminBootstrapState, 1)
        assert state.attempts == api.ATTEMPT_LIMIT
        state.window_started -= api.WINDOW_SECONDS
    assert (await post(harness, token=rotated)).status_code == 201


@pytest.mark.asyncio
async def test_permanent_after_deletion_and_secret_rotation(harness, monkeypatch):
    assert (await post(harness)).status_code == 201
    async with harness.factory.begin() as db:
        # Simulate future account deletion; no FK ties consumption to that row.
        await db.execute(delete(AuditLog))
        await db.execute(delete(User))
    monkeypatch.setattr(settings, "FIRST_ADMIN_BOOTSTRAP_TOKEN", SecretStr(TOKEN + "new"))
    assert (await post(harness, token=TOKEN + "new")).status_code == 409
    assert await counts(harness) == (0, 0)


@pytest.mark.asyncio
async def test_concurrent_requests_create_exactly_one(harness):
    responses = await asyncio.gather(post(harness), post(harness))
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert await counts(harness) == (1, 1)


@pytest.mark.asyncio
async def test_failure_rolls_back_user_audit_and_consumption(harness, monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise RuntimeError("synthetic-DB-URL-sentinel " + PASSWORD + TOKEN)
    with monkeypatch.context() as patch:
        patch.setattr(service, "record_audit_event", fail)
        response = await post(harness)
    assert response.status_code == 503
    assert all(secret not in response.text + caplog.text for secret in (PASSWORD, TOKEN, "synthetic-DB-URL-sentinel"))
    assert await counts(harness) == (0, 0)
    async with harness.factory() as db:
        state = await db.get(FirstAdminBootstrapState, 1)
        assert not state.consumed and state.attempts == 1
    assert (await post(harness)).status_code == 201


@pytest.mark.asyncio
async def test_missing_migration_state_fails_closed(harness):
    async with harness.factory.begin() as db:
        await db.execute(delete(FirstAdminBootstrapState))
    assert (await post(harness)).status_code == 503
    assert await counts(harness) == (0, 0)


@pytest.mark.asyncio
async def test_normal_login_and_admin_permissions_unchanged(harness, monkeypatch):
    assert (await post(harness)).status_code == 201
    monkeypatch.setattr(settings, "FIRST_ADMIN_BOOTSTRAP_TOKEN", None)
    assert (await post(harness)).status_code == 404
    response = await harness.client.post("/api/v1/auth/login", json={"username": BODY["username"], "password": PASSWORD})
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    assert (await harness.client.get("/api/v1/auth/me", headers=headers)).json()["role"] == "admin"
    response = await harness.client.post("/api/v1/auth/users", headers=headers,
        json={**BODY, "username": "staff-user", "email": "staff@example.com", "role": "investigator"})
    assert response.status_code == 201
    assert (await harness.client.post("/api/v1/auth/users", headers=headers, json={**BODY, "role": "admin"})).status_code == 422
    assert (await harness.client.post("/api/v1/auth/register", json=BODY)).status_code == 403
    assert (await harness.client.get("/api/v1/auth/me")).status_code == 401
    async with harness.factory.begin() as db:
        await db.execute(update(User).where(User.username == BODY["username"]).values(is_active=False))
    assert (await harness.client.get("/api/v1/auth/me", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_cli_and_http_share_one_time_guard(harness, monkeypatch):
    from app import provision_admin
    monkeypatch.setattr(provision_admin, "async_session_factory", harness.factory)
    await provision_admin.bootstrap(FirstAdminBootstrapRequest(**BODY))
    assert (await post(harness)).status_code == 409
    with pytest.raises(service.BootstrapUnavailable):
        await provision_admin.bootstrap(FirstAdminBootstrapRequest(**BODY))
    assert await counts(harness) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("demo", [True, False])
async def test_migration_consumes_existing_production_admin_only(tmp_path, demo):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(lambda sync: Base.metadata.create_all(sync, tables=[
                table for table in Base.metadata.sorted_tables if table.name != "first_admin_bootstrap_state"
            ]))
        factory = async_sessionmaker(engine)
        async with factory.begin() as db:
            db.add(User(username="existing", email="existing@example.com", full_name="Existing Admin",
                        hashed_password="unused", role=UserRole.ADMIN, is_demo_account=demo, is_active=False))
        migration = runpy.run_path(str(Path(__file__).parent / "alembic/versions/0009_first_admin_bootstrap.py"))

        def upgrade(sync):
            with Operations.context(MigrationContext.configure(sync)):
                migration["upgrade"]()

        async with engine.begin() as connection:
            await connection.run_sync(upgrade)
        async with factory() as db:
            state = await db.get(FirstAdminBootstrapState, 1)
            assert state.consumed is (not demo)
            assert state.attempts == 0
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_http_consumption_blocks_cli_after_admin_deletion(harness, monkeypatch):
    from app import provision_admin
    monkeypatch.setattr(provision_admin, "async_session_factory", harness.factory)
    assert (await post(harness)).status_code == 201
    async with harness.factory.begin() as db:
        await db.execute(delete(AuditLog))
        await db.execute(delete(User))
    with pytest.raises(service.BootstrapUnavailable):
        await provision_admin.bootstrap(FirstAdminBootstrapRequest(**BODY))


@pytest.mark.asyncio
async def test_authenticated_invalid_body_consumes_attempt(harness, monkeypatch):
    async def timed_out(request):
        raise TimeoutError()
    monkeypatch.setattr(api, "read_credentials", timed_out)
    assert (await post(harness)).status_code == 422
    async with harness.factory() as db:
        assert (await db.get(FirstAdminBootstrapState, 1)).attempts == 1
