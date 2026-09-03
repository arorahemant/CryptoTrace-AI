"""
CryptoTrace AI - Main FastAPI Application
Entry point for the backend API server.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.core.database import init_db, engine, async_session_factory
from app.core.security import get_password_hash
from app.api.auth import router as auth_router
from app.api.cases import router as cases_router
from app.models.models import User, UserRole

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def validate_runtime_mode():
    """Refuse non-demo startup until a live provider is actually configured."""
    if not settings.DEMO_MODE:
        raise RuntimeError(
            "A non-demo blockchain provider is not configured; keep DEMO_MODE=true "
            "until live provider integration is implemented and verified"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("🚀 Starting CryptoTrace AI Backend...")

    validate_runtime_mode()

    # Create tables
    await init_db()
    logger.info("✅ Database tables created")

    # Seed known demo accounts only in demo mode. Production accounts must be
    # provisioned through a controlled operator workflow.
    async with async_session_factory() as session:
        from sqlalchemy import select
        result = await session.execute(select(User).limit(1))
        if settings.DEMO_MODE and not result.scalars().first():
            demo_user = User(
                email="investigator@cryptotrace.ai",
                username="investigator",
                hashed_password=get_password_hash("investigate123"),
                full_name="Lead Investigator",
                role=UserRole.INVESTIGATOR,
            )
            session.add(demo_user)

            # Add supervisor
            supervisor = User(
                email="supervisor@cryptotrace.ai",
                username="supervisor",
                hashed_password=get_password_hash("supervisor123"),
                full_name="Senior Supervisor",
                role=UserRole.SUPERVISOR,
            )
            session.add(supervisor)

            await session.commit()
            logger.info("✅ Demo users created")

        # Ensure the RBAC foundation is complete even when an older demo DB
        # already contains the investigator/supervisor seed users.
        admin_result = await session.execute(select(User).where(User.username == "admin"))
        if settings.DEMO_MODE and not admin_result.scalars().first():
            session.add(User(
                email="admin@cryptotrace.ai",
                username="admin",
                hashed_password=get_password_hash("admin123"),
                full_name="Platform Administrator",
                role=UserRole.ADMIN,
            ))
            await session.commit()
            logger.info("✅ Demo admin created")

    logger.info(f"✅ CryptoTrace AI Backend ready (Demo Mode: {settings.DEMO_MODE})")

    yield

    # Shutdown
    await engine.dispose()
    logger.info("👋 CryptoTrace AI Backend shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Real-Time Identification of Fraud-Linked Cryptocurrency Exchanges from Victim-Reported Suspect Wallet Addresses",
    lifespan=lifespan,
)


@app.exception_handler(OperationalError)
async def database_unavailable_handler(request, exc: OperationalError):
    """Return a safe retryable response when the configured DB is unavailable."""
    logger.error("Database unavailable for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=503,
        content={"detail": "Database temporarily unavailable. Please retry."},
        headers={"Retry-After": "5"},
    )

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(cases_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
        "demo_mode": settings.DEMO_MODE,
    }


@app.get(f"{settings.API_PREFIX}/health", include_in_schema=False)
async def versioned_health_check():
    """Compatibility health endpoint used by API clients and smoke tests."""
    return await health_check()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.APP_NAME,
        "tagline": "One Wallet. Complete Investigation.",
        "version": settings.APP_VERSION,
        "api_docs": "/docs",
        "health": "/health",
    }
