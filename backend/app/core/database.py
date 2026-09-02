"""
CryptoTrace AI - Database Configuration
Async SQLAlchemy engine and session management.
Supports PostgreSQL (production) and SQLite (development/prototype).
"""
import os
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from app.core.config import settings


def _get_database_url() -> str:
    """
    Determine the database URL without weakening production configuration.

    SQLite is a deliberate local/demo fallback. Production must use the
    configured PostgreSQL URL and fails closed if a SQLite URL or override is
    supplied accidentally.
    """
    url = settings.DATABASE_URL
    sqlite_override = os.environ.get("USE_SQLITE", "").lower() == "true"

    if not settings.DEMO_MODE and ("sqlite" in url.lower() or sqlite_override):
        raise RuntimeError(
            "SQLite is only supported when DEMO_MODE=true; configure PostgreSQL for production"
        )

    # If explicitly set to SQLite, use as-is
    if "sqlite" in url.lower():
        return url

    # For prototype without Docker: fall back to SQLite
    # This allows the app to start immediately on any machine
    sqlite_default = "true" if settings.DEMO_MODE else "false"
    if os.environ.get("USE_SQLITE", sqlite_default).lower() == "true":
        db_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "cryptotrace.db",
        )
        return f"sqlite+aiosqlite:///{db_path}"

    return url


DATABASE_URL = _get_database_url()
IS_SQLITE = "sqlite" in DATABASE_URL

engine_kwargs = {
    "echo": False,  # Reduce noise
}

if not IS_SQLITE:
    engine_kwargs.update({
        "pool_size": 20,
        "max_overflow": 10,
        "pool_pre_ping": True,
    })

engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# SQLite needs special handling for foreign keys
if IS_SQLITE:
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """Dependency that yields a database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
