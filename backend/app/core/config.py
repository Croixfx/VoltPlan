import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(Path(__file__).parent.parent.parent, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "VoltPlan Backend"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    # Database
    DATABASE_URL: str = "sqlite:///./voltplan.db"

    # Storage
    UPLOAD_DIR: str = os.path.join(Path(__file__).parent.parent.parent, "uploads")
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "png", "jpg", "jpeg"]

    # AI Configuration
    # Supported: "mock", "gemini", "openai"
    AI_PROVIDER: str = "mock"
    GEMINI_API_KEY: str = ""
    # Verified end to end on a real plan. Models get retired: GET /api/ai/check tells you if this one is still
    # available to your key and lists the alternatives (e.g. the maintained alias gemini-flash-latest).
    GEMINI_MODEL: str = "gemini-3.5-flash-lite"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # Access control for a deployed instance. Empty = no protection (local development).
    # When set, all routes except /api/health require the header X-API-Key.
    API_KEY: str = ""

    # Per-user login. AUTH_SECRET signs session tokens and must NOT be the API_KEY (the API key ships inside the
    # mobile app). Empty = login switched off (local development, tests); production refuses to start without it.
    AUTH_SECRET: str = ""
    AUTH_TOKEN_DAYS: int = 30
    # Projects created before accounts existed have no owner; the account with this email receives them when it
    # signs in. Leave empty to leave them unowned (and therefore invisible).
    LEGACY_OWNER_EMAIL: str = ""
    # Comma-separated emails of administrators: they can see and open every user's projects and manage accounts.
    # Register the admin account yourself right after setting this (an email nobody has verified).
    ADMIN_EMAILS: str = ""

    # Engineering Standard
    DEFAULT_STANDARD: str = "RS IEC 60364"


settings = Settings()

# Ensure uploads directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
