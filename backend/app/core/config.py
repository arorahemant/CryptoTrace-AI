"""
CryptoTrace AI - Application Configuration
Loads settings from environment variables with sensible defaults.
"""
import secrets
from typing import Optional
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_MIN_SECRET_KEY_LENGTH = 32
_UNSAFE_SECRET_PREFIXES = (
    "change-me-in-production",
    "change_me_in_production",
    "changeme",
    "default",
    "development",
    "test-secret",
)
_LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _is_unsafe_secret(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        len(normalized) < _MIN_SECRET_KEY_LENGTH
        or len(set(normalized)) < 4
        or any(normalized.startswith(prefix) for prefix in _UNSAFE_SECRET_PREFIXES)
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    _LOCAL_CORS_ORIGINS = (
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    )

    # Application
    APP_NAME: str = "CryptoTrace AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"
    # Comma-separated exact browser/native origins. Demo mode defaults to the
    # local frontend; production must provide its deployed origin(s).
    CORS_ORIGINS: Optional[str] = None

    # Database
    # Demo mode may omit DATABASE_URL and use the explicit SQLite fallback.
    # Hosted non-demo mode must inject a PostgreSQL URL.
    DATABASE_URL: Optional[str] = None
    # Reserved for future synchronous migration tooling; the current runtime
    # uses only DATABASE_URL through the async SQLAlchemy engine.
    DATABASE_SYNC_URL: Optional[str] = None

    # Authentication
    # A production signing key must be injected through the environment (or a
    # secrets manager). Demo mode gets an ephemeral process key when no key is
    # configured, which keeps local startup convenient without embedding a
    # reusable signing secret in source.
    SECRET_KEY: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    ALGORITHM: str = "HS256"

    # Blockchain Providers
    ETHERSCAN_API_KEY: Optional[str] = None
    BLOCKCHAIN_RPC_URL: Optional[str] = None

    # AI / LLM
    OPENAI_API_KEY: Optional[str] = None
    AI_MODEL: str = "gpt-4"

    # Tracing Defaults
    MAX_TRACE_HOPS: int = 5
    MAX_TRACE_TRANSACTIONS: int = 200
    TRACE_TIME_WINDOW_HOURS: int = 720  # 30 days
    MIN_TRACE_AMOUNT: float = 0.001

    # Demo Mode
    DEMO_MODE: bool = True

    @model_validator(mode="after")
    def validate_production_configuration(self):
        configured_secret = (self.SECRET_KEY or "").strip()
        if _is_unsafe_secret(configured_secret):
            if not self.DEMO_MODE:
                raise ValueError(
                    "SECRET_KEY must be a configured random value of at least 32 characters when DEMO_MODE=false"
                )
            self.SECRET_KEY = secrets.token_urlsafe(32)
        else:
            self.SECRET_KEY = configured_secret

        if not self.DEMO_MODE:
            database_url = (self.DATABASE_URL or "").strip()
            if not database_url:
                raise ValueError(
                    "DATABASE_URL must be configured when DEMO_MODE=false"
                )

            parsed_database_url = urlparse(database_url)
            if parsed_database_url.hostname in _LOCAL_DATABASE_HOSTS:
                raise ValueError(
                    "DATABASE_URL must not target localhost when DEMO_MODE=false"
                )
            if "sqlite" in database_url.lower():
                raise ValueError(
                    "DATABASE_URL must use PostgreSQL when DEMO_MODE=false"
                )
            if self.DEBUG:
                raise ValueError("DEBUG must be false when DEMO_MODE=false")

            # Evaluate the property during settings construction so hosted
            # startup fails before the FastAPI app is created.
            self.cors_origins
        return self

    @property
    def cors_origins(self) -> list[str]:
        """Return the exact origins allowed to call the API."""
        raw_origins = self.CORS_ORIGINS
        if raw_origins is None:
            if self.DEMO_MODE:
                return list(self._LOCAL_CORS_ORIGINS)
            raise ValueError(
                "CORS_ORIGINS must be configured when DEMO_MODE=false"
            )

        origins = [
            origin.strip().rstrip("/")
            for origin in raw_origins.split(",")
            if origin.strip()
        ]
        if "*" in origins:
            raise ValueError(
                "CORS_ORIGINS must contain explicit origins; '*' is incompatible with credentials"
            )
        if not origins:
            raise ValueError(
                "CORS_ORIGINS must contain at least one explicit origin"
            )
        return origins


settings = Settings()
