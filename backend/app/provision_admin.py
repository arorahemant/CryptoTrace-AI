"""Operator-only first admin bootstrap: python -m app.provision_admin.

Run against the intended, migrated database. Passwords are read interactively,
never through command arguments, environment defaults, or committed values.
"""
import asyncio
import getpass
from sqlalchemy import select
from app.core.database import async_session_factory
from app.core.security import get_password_hash
from app.models.models import User, UserRole, ReporterAccount
from app.schemas.schemas import StaffProvisionRequest
from app.core.audit import record_audit_event


async def bootstrap(request: StaffProvisionRequest):
    async with async_session_factory() as db:
        async with db.begin():
            if db.bind.dialect.name == "postgresql":
                from sqlalchemy import text
                await db.execute(text("SELECT pg_advisory_xact_lock(2618301)"))
            if await db.scalar(select(User.id).where(User.role == UserRole.ADMIN, User.is_demo_account.is_(False))):
                raise RuntimeError("An operator-provisioned administrator already exists")
            for model in (User, ReporterAccount):
                if await db.scalar(select(model.id).where((model.username == request.username) | (model.email == request.email))):
                    raise RuntimeError("Account identity already exists")
            user = User(username=request.username, email=request.email, full_name=request.full_name,
                        hashed_password=get_password_hash(request.password), role=UserRole.ADMIN,
                        is_active=True, is_demo_account=False)
            db.add(user)
            await db.flush()
            record_audit_event(db, user=user, action="operator_admin_bootstrapped", resource_type="user", resource_id=str(user.id))


if __name__ == "__main__":
    username = input("Administrator username: ").strip()
    email = input("Administrator email: ").strip()
    full_name = input("Administrator name: ").strip()
    password = getpass.getpass("Password (12–72 characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    request = StaffProvisionRequest(username=username, email=email, full_name=full_name, password=password)
    asyncio.run(bootstrap(request))
    print("Administrator provisioned")
