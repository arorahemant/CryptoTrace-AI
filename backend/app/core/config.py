"""
CryptoTrace AI - Application Configuration
Loads settings from environment variables with sensible defaults.
"""
import secrets
from typing import Optional

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


def _is_unsafe_secret(value: str) -> bool:
    normalized = value.strip().lower()
    return (
        len(normalized) < _MIN_SECRET_KEY_LENGTH
        or len(set(normalized)) < 4
        or any(normalized.startswith(prefix) for prefix in _UNSAFE_SECRET_PREFIXES)
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Application
    APP_NAME: str = "CryptoTrace AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://cryptotrace:cryptotrace@localhost:5432/cryptotrace"
    DATABASE_SYNC_URL: str = "postgresql://cryptotrace:cryptotrace@localhost:5432/cryptotrace"

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
    def validate_secret_key(self):
        configured_secret = (self.SECRET_KEY or "").strip()
        if _is_unsafe_secret(configured_secret):
            if not self.DEMO_MODE:
                raise ValueError(
                    "SECRET_KEY must be a configured random value of at least 32 characters when DEMO_MODE=false"
                )
            self.SECRET_KEY = secrets.token_urlsafe(32)
        else:
            self.SECRET_KEY = configured_secret
        return self


settings = Settings()
