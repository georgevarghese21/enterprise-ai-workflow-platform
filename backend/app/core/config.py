from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "NovaTech AI Workflow Automation Platform"
    environment: str = "development"
    log_level: str = "INFO"

    database_url: str = (
        "postgresql+psycopg://novatech:novatech@localhost:5432/novatech"
    )

    # LLM configuration (wired up starting Phase 3). LLM_MODE=mock avoids
    # any external API calls and is used in tests and CI.
    llm_mode: str = "mock"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    embedding_provider: str = "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
