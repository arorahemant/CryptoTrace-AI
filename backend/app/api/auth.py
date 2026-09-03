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
from app.models.models import (
    InvestigatorPublicProfile,
    ReporterAccount,
    User,
    UserRole,
)
from app.schemas.schemas import (
    InvestigatorPublicProfileResponse,
    InvestigatorPublicProfileUpdate,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    ReporterRegisterRequest,
    UserResponse,
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
    role = user.role.value if user else None

    if not user:
        reporter_result = await db.execute(
            select(ReporterAccount).where(ReporterAccount.username == request.username)
        )
        user = reporter_result.scalars().first()
        role = "reporter" if user else None

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
        data={"sub": str(user.id), "role": role}
    )

    return LoginResponse(
        access_token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            role=role,
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
    reporter_existing = await db.execute(
        select(ReporterAccount).where(
            (ReporterAccount.email == request.email) |
            (ReporterAccount.username == request.username)
        )
    )
    if existing.scalars().first() or reporter_existing.scalars().first():
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


@router.post("/reporter/register", response_model=UserResponse)
async def register_reporter(
    request: ReporterRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a non-privileged reporter account."""
    investigator_existing = await db.execute(
        select(User).where(
            (User.email == request.email) | (User.username == request.username)
        )
    )
    reporter_existing = await db.execute(
        select(ReporterAccount).where(
            (ReporterAccount.email == request.email) |
            (ReporterAccount.username == request.username)
        )
    )
    if investigator_existing.scalars().first() or reporter_existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account with this email or username already exists",
        )

    reporter = ReporterAccount(
        email=request.email,
        username=request.username,
        hashed_password=get_password_hash(request.password),
        full_name=request.full_name,
    )
    db.add(reporter)
    await db.flush()
    await db.refresh(reporter)
    return UserResponse(
        id=reporter.id,
        email=reporter.email,
        username=reporter.username,
        full_name=reporter.full_name,
        role="reporter",
        is_active=reporter.is_active,
        created_at=reporter.created_at,
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

    if payload.get("role") == "reporter":
        raise HTTPException(status_code=403, detail="Investigator access required")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user = await db.get(User, uuid.UUID(user_id))
    except (ValueError, AttributeError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid token payload")
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    return user


@router.get("/me/public-profile", response_model=InvestigatorPublicProfileResponse)
async def get_public_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current investigator's persisted reporter-visible profile."""
    profile = await db.get(InvestigatorPublicProfile, current_user.id)
    if not profile:
        raise HTTPException(status_code=404, detail="Public profile not configured")
    return profile


@router.put("/me/public-profile", response_model=InvestigatorPublicProfileResponse)
async def update_public_profile(
    request: InvestigatorPublicProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist the investigator fields explicitly approved for reporters."""
    profile = await db.get(InvestigatorPublicProfile, current_user.id)
    if profile:
        profile.display_name = request.display_name.strip()
        profile.role_title = request.role_title.strip()
        profile.is_reporter_visible = request.is_reporter_visible
    else:
        profile = InvestigatorPublicProfile(
            user_id=current_user.id,
            display_name=request.display_name.strip(),
            role_title=request.role_title.strip(),
            is_reporter_visible=request.is_reporter_visible,
        )
        db.add(profile)
    await db.flush()
    await db.refresh(profile)
    return profile
