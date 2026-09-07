from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved from this file's location (not cwd) so it works the same whether
# the backend runs from the repo root, from `backend/`, or inside Docker
# (where docker-compose mounts the repo's `data/` dir at container path
# `/data`, which lands here too: /app/app/core/config.py -> parents[3] == /).
_DEFAULT_POLICIES_DIR = str(Path(__file__).resolve().parents[3] / "data" / "policies")


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
    policies_dir: str = _DEFAULT_POLICIES_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()
