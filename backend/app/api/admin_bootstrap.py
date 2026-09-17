"""One-time, explicitly enabled admin bootstrap. Never returns credentials."""
import asyncio
import hmac
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.core.database import get_db
from app.core.admin_bootstrap import (
    BootstrapIdentityConflict, bootstrap_unavailable, create_first_admin, lock_bootstrap,
)
from app.schemas.schemas import FirstAdminBootstrapRequest

router = APIRouter(prefix="/auth", tags=["Operator bootstrap"])
HEADER = "X-First-Admin-Bootstrap-Token"
ATTEMPT_LIMIT = 10
WINDOW_SECONDS = 900
MAX_BODY_BYTES = 8192


def reply(status, detail):
    return JSONResponse(status_code=status, content={"detail": detail}, headers={"Cache-Control": "no-store"})


async def read_credentials(request):
    # Parse manually so FastAPI/Pydantic never echo secret input in a 422 response.
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_BODY_BYTES:
            raise ValueError("Body too large")
        body.extend(chunk)
    return FirstAdminBootstrapRequest.model_validate_json(bytes(body))


@router.post("/bootstrap-first-admin", status_code=201)
async def bootstrap_first_admin(request: Request, db: AsyncSession = Depends(get_db)):
    configured = settings.FIRST_ADMIN_BOOTSTRAP_TOKEN
    secret = configured.get_secret_value() if configured else ""
    # Invalid configuration disables only this optional feature, never login.
    if not (32 <= len(secret) <= 128 and secret.isascii() and not any(c.isspace() for c in secret)):
        return reply(404, "Bootstrap unavailable")
    try:
        # Reserve an attempt durably before token/body validation. This global
        # budget is shared by workers and survives restarts and token rotation.
        async with db.begin():
            state = await lock_bootstrap(db)
            if await bootstrap_unavailable(db, state):
                denial = reply(409, "Bootstrap unavailable")
            else:
                now = time.time()
                if now - state.window_started >= WINDOW_SECONDS:
                    state.window_started, state.attempts = now, 0
                if state.attempts >= ATTEMPT_LIMIT:
                    denial = reply(429, "Bootstrap attempt limit reached. Try again later.")
                else:
                    state.attempts += 1
                    denial = None
        if denial is not None:
            return denial

        tokens = request.headers.getlist(HEADER)
        supplied = tokens[0] if len(tokens) == 1 else ""
        if len(supplied) > 128 or not hmac.compare_digest(supplied.encode("utf-8"), secret.encode("utf-8")):
            return reply(403, "Bootstrap denied")
        try:
            credentials = await asyncio.wait_for(read_credentials(request), timeout=5)
        except (ValidationError, ValueError, TimeoutError):
            return reply(422, "Invalid bootstrap request")

        async with db.begin():
            state = await lock_bootstrap(db)
            # Recheck after reading the body: another HTTP/CLI request may win.
            if await bootstrap_unavailable(db, state):
                result = reply(409, "Bootstrap unavailable")
            else:
                await create_first_admin(db, state, credentials, request_context=request)
                result = reply(201, "Administrator provisioned")
        return result
    except (BootstrapIdentityConflict, IntegrityError):
        return reply(409, "Bootstrap request conflicts with an existing account")
    except Exception:
        # Do not log exceptions: DB/validation/driver failures can contain input,
        # connection details or SQL parameters. Transaction contexts roll back.
        return reply(503, "Bootstrap unavailable")
