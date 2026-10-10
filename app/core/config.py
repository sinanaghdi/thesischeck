"""Environment-backed configuration. Secrets must be supplied at deployment time."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_name: str = "ThesisCheck"
    app_env: str = "development"
    debug: bool = False
    database_url: str = "sqlite:///./data/thesischeck.db"
    max_upload_mb: int = Field(default=30, ge=1, le=100)
    inspection_rate_limit: int = Field(default=20, ge=1, le=1000)
    inspection_rate_window_seconds: int = Field(default=60, ge=1, le=3600)
    file_retention_days: int = Field(default=7, ge=1, le=365)
    llm_mode: str = "off"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_max_tokens_per_job: int = Field(default=12000, ge=0, le=100000)
    jwt_secret: str = "development-only-change-me"
    cors_origins: str = "http://127.0.0.1:8000,http://localhost:8000"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()
