"""Schema migration checkpoint checks against the active local database."""
import asyncio

from sqlalchemy import inspect, text

from app.core.database import engine


def test_asset_action_schema_is_versioned_and_present():
    async def read_schema():
        async with engine.connect() as connection:
            version = await connection.scalar(text("SELECT version_num FROM alembic_version"))
            tables = await connection.run_sync(
                lambda sync_connection: set(inspect(sync_connection).get_table_names())
            )
            return version, tables

    version, tables = asyncio.run(read_schema())
    assert version == "0004_asset_action_attribution"
    assert {
        "investigator_public_profiles",
        "reporter_accounts",
        "reporter_submissions",
        "asset_action_requests",
    } <= tables
