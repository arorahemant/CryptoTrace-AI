"""Focused coverage for the hosted reporter-only demo login gate."""
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.auth import _failed_logins, router as auth_router
from app.api.reporter import router as reporter_router
from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import get_password_hash
from app.main import capabilities
from app.models.models import ReporterAccount, User, UserRole


@pytest_asyncio.fixture
async def harness(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reporter-demo.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory.begin() as db:
        db.add_all([
            ReporterAccount(
                username="reporter", email="reporter@cryptotrace.ai", full_name="Demo Reporter",
                hashed_password=get_password_hash("report123"), is_demo_account=True,
            ),
            User(
                username="investigator", email="investigator@cryptotrace.ai", full_name="Demo Investigator",
                hashed_password=get_password_hash("investigate123"), role=UserRole.INVESTIGATOR,
                is_demo_account=True,
            ),
            User(
                username="admin", email="admin@cryptotrace.ai", full_name="Demo Admin",
                hashed_password=get_password_hash("admin123"), role=UserRole.ADMIN, is_demo_account=True,
            ),
            User(
                username="production-admin", email="operator@example.com", full_name="Production Admin",
                hashed_password=get_password_hash("synthetic-production-password"), role=UserRole.ADMIN,
                is_demo_account=False,
            ),
            User(
                username="production-investigator", email="analyst@example.com", full_name="Production Investigator",
                hashed_password=get_password_hash("synthetic-investigator-password"), role=UserRole.INVESTIGATOR,
                is_demo_account=False,
            ),
        ])

    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "SEED_DEMO_ACCOUNTS", False)
    monkeypatch.setattr(settings, "REPORTER_DEMO_LOGIN_ENABLED", True)
    _failed_logins.clear()

    app = FastAPI()
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(reporter_router, prefix="/api/v1")

    async def session():
        async with factory() as db:
            yield db

    app.dependency_overrides[get_db] = session
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://test") as client:
        yield SimpleNamespace(client=client)
    _failed_logins.clear()
    await engine.dispose()


async def login(harness, username, password):
    return await harness.client.post("/api/v1/auth/login", json={"username": username, "password": password})


@pytest.mark.asyncio
async def test_capability_separates_reporter_and_staff_demo_login(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    monkeypatch.setattr(settings, "SEED_DEMO_ACCOUNTS", False)
    monkeypatch.setattr(settings, "REPORTER_DEMO_LOGIN_ENABLED", True)

    response = await capabilities()

    assert response["reporter_demo_login_available"] is True
    assert response["demo_login_available"] is False


@pytest.mark.asyncio
async def test_reporter_only_demo_gate_and_production_accounts(harness):
    reporter = await login(harness, "reporter", "report123")
    assert reporter.status_code == 200
    assert reporter.json()["user"]["role"] == "reporter"

    assert (await login(harness, "investigator", "investigate123")).status_code == 403
    assert (await login(harness, "admin", "admin123")).status_code == 403

    production_admin = await login(harness, "production-admin", "synthetic-production-password")
    production_investigator = await login(harness, "production-investigator", "synthetic-investigator-password")
    assert production_admin.status_code == 200
    assert production_investigator.status_code == 200

    reporter_headers = {"Authorization": f"Bearer {reporter.json()['access_token']}"}
    assert (await harness.client.get("/api/v1/reporter/submissions", headers=reporter_headers)).status_code == 200
    denied = await harness.client.get("/api/v1/auth/me", headers=reporter_headers)
    assert denied.status_code == 403
    assert denied.json()["detail"] == "Investigator access required"
