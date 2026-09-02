"""
CryptoTrace AI - Application Configuration
Loads settings from environment variables with sensible defaults.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


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
    SECRET_KEY: str = "CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32"
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

settings = Settings()

if not settings.DEMO_MODE and settings.SECRET_KEY.lower().startswith("change-me-in-production"):
    raise RuntimeError("SECRET_KEY must be set to a strong value when DEMO_MODE=false")
