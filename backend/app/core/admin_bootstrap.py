"""Shared transactional first-admin guard for the HTTP and operator CLI paths."""
from sqlalchemy import select, text, update

from app.core.audit import record_audit_event
from app.core.security import get_password_hash
from app.models.models import FirstAdminBootstrapState, ReporterAccount, User, UserRole


class BootstrapUnavailable(Exception):
    pass


class BootstrapIdentityConflict(Exception):
    pass


async def lock_bootstrap(db):
    if db.bind.dialect.name == "postgresql":
        # Also coordinates with the already deployed operator CLI.
        await db.execute(text("SELECT pg_advisory_xact_lock(2618301)"))
    # UPDATE acquires a write lock on both PostgreSQL and SQLite. Missing state
    # fails closed: only the migration may initialize it.
    result = await db.execute(update(FirstAdminBootstrapState).where(
        FirstAdminBootstrapState.id == 1
    ).values(id=1))
    if result.rowcount != 1:
        raise BootstrapUnavailable()
    return await db.get(FirstAdminBootstrapState, 1, populate_existing=True)


async def bootstrap_unavailable(db, state):
    if state.consumed:
        return True
    if await db.scalar(select(User.id).where(
        User.role == UserRole.ADMIN, User.is_demo_account.is_(False)
    ).limit(1)):
        state.consumed = True
        return True
    return False


async def create_first_admin(db, state, request, *, request_context=None):
    """Caller holds the bootstrap lock and commits account, audit and state together."""
    for model in (User, ReporterAccount):
        if await db.scalar(select(model.id).where(
            (model.username == request.username) | (model.email == request.email)
        ).limit(1)):
            raise BootstrapIdentityConflict()
    user = User(
        username=request.username, email=request.email, full_name=request.full_name,
        hashed_password=get_password_hash(request.password.get_secret_value()),
        role=UserRole.ADMIN, is_active=True, is_demo_account=False,
    )
    db.add(user)
    await db.flush()
    record_audit_event(
        db, user=user, action="operator_admin_bootstrapped", resource_type="user",
        resource_id=str(user.id), request=request_context,
    )
    state.consumed = True
