"""Regression coverage for the P0 authentication and investigation risks."""

from pathlib import Path
import asyncio
import uuid

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from fastapi.routing import APIRoute

from app.api.cases import _get_authorized_case, _get_user, router
from app.core.config import Settings, settings
from app.core.database import Base, _get_database_url
from app.core.security import create_access_token, decode_access_token
from app.models.models import (
    Case,
    CaseStatus,
    Blockchain,
    Evidence,
    FundFlow,
    InvestigationEvent,
    PatternFinding,
    RiskAssessment,
    Transaction,
    User,
    UserRole,
    VASPAttribution,
    Wallet,
)
from app.services.investigation_service import InvestigationService


@pytest.mark.parametrize(
    "unsafe_secret",
    [None, "short", "change-me-in-production-use-openssl-rand-hex-32"],
)
def test_production_rejects_missing_or_unsafe_secret(unsafe_secret):
    with pytest.raises(ValidationError):
        Settings(DEMO_MODE=False, SECRET_KEY=unsafe_secret, _env_file=None)


def test_demo_secret_is_ephemeral_and_jwt_round_trip_works():
    demo_settings = Settings(DEMO_MODE=True, SECRET_KEY=None, _env_file=None)

    assert len(demo_settings.SECRET_KEY) >= 32
    assert demo_settings.SECRET_KEY != "change-me-in-production-use-openssl-rand-hex-32"

    token = create_access_token({"sub": "security-regression"})
    payload = decode_access_token(token)
    assert payload and payload["sub"] == "security-regression"
    assert decode_access_token(token[:-1] + ("a" if token[-1] != "a" else "b")) is None


def test_valid_production_secret_is_accepted_without_embedding_a_secret():
    configured = "prod-key-" + ("a9" * 24)
    settings = Settings(DEMO_MODE=False, SECRET_KEY=configured, _env_file=None)

    assert settings.SECRET_KEY == configured
    source = Path(__file__).parent / "app" / "core" / "config.py"
    source_text = source.read_text(encoding="utf-8")
    assert 'SECRET_KEY: str = "' not in source_text
    assert 'SECRET_KEY: Optional[str] = "' not in source_text


def test_production_rejects_explicit_sqlite_database_url(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite+aiosqlite:///unsafe-production.db")
    monkeypatch.delenv("USE_SQLITE", raising=False)

    with pytest.raises(RuntimeError, match="SQLite is only supported"):
        _get_database_url()


def test_production_rejects_sqlite_override(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql+asyncpg://configured")
    monkeypatch.setenv("USE_SQLITE", "true")

    with pytest.raises(RuntimeError, match="configure PostgreSQL"):
        _get_database_url()


def test_each_case_route_resolves_one_user_dependency():
    routes = [route for route in router.routes if isinstance(route, APIRoute)]

    assert routes
    assert all(
        sum(dependency.call is _get_user for dependency in route.dependant.dependencies) == 1
        for route in routes
    )


@pytest.mark.asyncio
async def test_authorized_case_check_does_not_reload_user():
    user = User(id=uuid.uuid4(), role=UserRole.INVESTIGATOR, is_active=True)
    case = Case(id=uuid.uuid4(), investigator_id=user.id)

    class CaseOnlySession:
        def __init__(self):
            self.get_calls = []

        async def get(self, model, identifier):
            self.get_calls.append((model, identifier))
            return case

    db = CaseOnlySession()
    resolved = await _get_authorized_case(str(case.id), db, user)

    assert resolved is case
    assert db.get_calls == [(Case, case.id)]


@pytest_asyncio.fixture
async def investigation_session_factory(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'p0-remediation.db'}"
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        yield session_factory
    finally:
        await engine.dispose()


async def _create_demo_case(session_factory) -> str:
    case_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(
            User(
                id=uuid.uuid4(),
                email=f"{case_id}@example.com",
                username=f"p0-{case_id.hex}",
                hashed_password="not-used-in-service-test",
                full_name="P0 Regression User",
                role=UserRole.INVESTIGATOR,
            )
        )
        user = (await db.execute(select(User))).scalars().first()
        db.add(
            Case(
                id=case_id,
                case_number=f"CT-P0-{case_id.hex[:8]}",
                title="P0 idempotency regression",
                reported_wallet="0xReported001",
                blockchain=Blockchain.DEMO,
                status=CaseStatus.NEW,
                investigator_id=user.id,
                is_demo=True,
            )
        )
        await db.commit()
    return str(case_id)


async def _counts(db, case_id: str):
    case_uuid = uuid.UUID(case_id)
    models = (
        Wallet,
        Transaction,
        PatternFinding,
        Evidence,
        InvestigationEvent,
        FundFlow,
        RiskAssessment,
        VASPAttribution,
    )
    counts = []
    for model in models:
        counts.append(
            await db.scalar(
                select(func.count()).select_from(model).where(model.case_id == case_uuid)
            )
        )
    return tuple(counts)


@pytest.mark.asyncio
async def test_repeated_investigation_reuses_one_persisted_snapshot(
    investigation_session_factory,
):
    case_id = await _create_demo_case(investigation_session_factory)

    async with investigation_session_factory() as db:
        first = await InvestigationService(db).run_investigation(case_id)
        await db.commit()
        first_counts = await _counts(db, case_id)

        second = await InvestigationService(db).run_investigation(case_id)
        await db.commit()
        second_counts = await _counts(db, case_id)

        third = await InvestigationService(db).run_investigation(case_id)
        await db.commit()
        third_counts = await _counts(db, case_id)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert third["status"] == "completed"
    assert first_counts == second_counts == third_counts
    assert first_counts[0] == 9
    assert first_counts[1] == 10
    assert first_counts[2] == 9
    assert first_counts[3] == 12
    assert first_counts[4] == 10
    assert first_counts[5] == 10
    assert first_counts[6] == 9
    assert first_counts[7] == 1
    assert second["stats"]["total_transactions"] == first["stats"]["total_transactions"]
    assert {node["id"] for node in second["graph"]["nodes"]} == {
        node["id"] for node in first["graph"]["nodes"]
    }
    assert {
        (edge["source"], edge["target"], edge["hash"])
        for edge in second["graph"]["edges"]
    } == {
        (edge["source"], edge["target"], edge["hash"])
        for edge in first["graph"]["edges"]
    }


@pytest.mark.asyncio
async def test_concurrent_investigation_requests_do_not_duplicate_rows(
    investigation_session_factory,
):
    case_id = await _create_demo_case(investigation_session_factory)

    async def run_and_commit():
        async with investigation_session_factory() as db:
            result = await InvestigationService(db).run_investigation(case_id)
            await db.commit()
            return result

    results = await asyncio.gather(run_and_commit(), run_and_commit())

    async with investigation_session_factory() as db:
        counts = await _counts(db, case_id)

    assert all(result["status"] == "completed" for result in results)
    assert counts == (9, 10, 9, 12, 10, 10, 9, 1)


class FailAfterTransactionQueue(InvestigationService):
    async def _save_transactions(self, case, transactions, chain):
        await super()._save_transactions(case, transactions, chain)
        raise RuntimeError("simulated persistence failure")


@pytest.mark.asyncio
async def test_failed_investigation_rolls_back_and_can_be_retried(
    investigation_session_factory,
):
    case_id = await _create_demo_case(investigation_session_factory)

    async with investigation_session_factory() as db:
        with pytest.raises(RuntimeError, match="simulated persistence failure"):
            await FailAfterTransactionQueue(db).run_investigation(case_id)
        await db.rollback()

        failed_counts = await _counts(db, case_id)
        case = await db.get(Case, uuid.UUID(case_id))
        assert failed_counts == (0, 0, 0, 0, 0, 0, 0, 0)
        assert case.status == CaseStatus.NEW

        result = await InvestigationService(db).run_investigation(case_id)
        await db.commit()
        retry_counts = await _counts(db, case_id)

    assert result["status"] == "completed"
    assert retry_counts == (9, 10, 9, 12, 10, 10, 9, 1)
