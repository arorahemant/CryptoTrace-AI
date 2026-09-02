"""
CryptoTrace AI - Authentication API
JWT-based authentication with role-based access control.
"""
import time
import uuid
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import verify_password, get_password_hash, create_access_token, decode_access_token
from app.models.models import User, UserRole
from app.schemas.schemas import (
    LoginRequest, LoginResponse, RegisterRequest, UserResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Lightweight per-process protection for the demo/prototype. Production should
# enforce the same policy at the API gateway or with a shared rate-limit store.
_FAILED_LOGIN_LIMIT = 5
_FAILED_LOGIN_WINDOW_SECONDS = 60
_failed_logins: dict[str, list[float]] = defaultdict(list)


def _check_login_rate_limit(client_key: str) -> None:
    now = time.monotonic()
    attempts = [
        timestamp
        for timestamp in _failed_logins[client_key]
        if now - timestamp < _FAILED_LOGIN_WINDOW_SECONDS
    ]
    _failed_logins[client_key] = attempts
    if len(attempts) >= _FAILED_LOGIN_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Try again later.",
            headers={"Retry-After": str(_FAILED_LOGIN_WINDOW_SECONDS)},
        )


def _record_failed_login(client_key: str) -> None:
    _failed_logins[client_key].append(time.monotonic())


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    request_context: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return JWT token."""
    client_key = request_context.client.host if request_context.client else "unknown"
    _check_login_rate_limit(client_key)
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    user = result.scalars().first()

    if not user or not verify_password(request.password, user.hashed_password):
        _record_failed_login(client_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    _failed_logins.pop(client_key, None)
    token = create_access_token(
        data={"sub": str(user.id), "role": user.role.value}
    )

    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=user.role.value,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/register", response_model=UserResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new user."""
    # Check existing
    existing = await db.execute(
        select(User).where(
            (User.email == request.email) | (User.username == request.username)
        )
    )
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email or username already exists",
        )

    user = User(
        email=request.email,
        username=request.username,
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name,
        # Public registration cannot self-assign privileged roles. Supervisors
        # and admins must be provisioned by an administrator.
        role=UserRole.INVESTIGATOR,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role.value,
        is_active=user.is_active,
        created_at=user.created_at,
    )


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> User:
    """Dependency to get the current authenticated user from JWT."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = decode_access_token(authorization[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user = await db.get(User, uuid.UUID(user_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token payload")
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
