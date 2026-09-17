"""Operator-only first admin bootstrap: python -m app.provision_admin.

Run against the intended, migrated database. Passwords are read interactively,
never through command arguments, environment defaults, or committed values.
"""
import asyncio
import getpass
import sys
import warnings
from app.core.database import async_session_factory
from app.schemas.schemas import FirstAdminBootstrapRequest
from app.core.admin_bootstrap import (
    BootstrapUnavailable, bootstrap_unavailable, create_first_admin, lock_bootstrap,
)


async def bootstrap(request: FirstAdminBootstrapRequest):
    async with async_session_factory() as db:
        async with db.begin():
            state = await lock_bootstrap(db)
            unavailable = await bootstrap_unavailable(db, state)
            if not unavailable:
                await create_first_admin(db, state, request)
        if unavailable:
            raise BootstrapUnavailable()


if __name__ == "__main__":
    if not sys.stdin.isatty():
        raise SystemExit("An interactive terminal is required")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            username = input("Administrator username: ").strip()
            email = input("Administrator email: ").strip()
            full_name = input("Administrator name: ").strip()
            password = getpass.getpass("Password (12-72 characters; maximum 72 UTF-8 bytes): ")
            if password != getpass.getpass("Confirm password: "):
                raise SystemExit("Passwords do not match")
        request = FirstAdminBootstrapRequest(username=username, email=email, full_name=full_name, password=password)
        asyncio.run(bootstrap(request))
    except Exception:
        raise SystemExit("Bootstrap failed: verify account identity, database readiness and bootstrap availability") from None
    print("Administrator provisioned")
