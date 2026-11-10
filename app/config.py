import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./kasparro.db"
    EXECUTION_MODE: str = "replay"

    ANALYST_TOKEN: str = "dev-analyst-token-2026"
    SECONDARY_ANALYST_TOKEN: Optional[str] = None
    REVIEWER_TOKEN: str = "dev-reviewer-token-2026"
    ADMIN_TOKEN: Optional[str] = None

    ALLOWED_IMPORT_DIRS: str = "data,fixtures"
    MAX_REQUEST_BODY_BYTES: int = 12 * 1024 * 1024
    MAX_IMPORT_FILE_BYTES: int = 10 * 1024 * 1024
    MAX_IMPORT_RECORDS_PER_FILE: int = 10000
    MAX_ANALYSIS_SECONDS: int = 120

    LLM_PROVIDER: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_TIMEOUT_SECONDS: int = 20
    LLM_MAX_RETRIES: int = 2

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()

