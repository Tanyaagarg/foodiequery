"""
config.py
---------
One place that reads every setting from the .env file in the project root.

Why a settings class instead of calling os.getenv() all over the codebase:
if a value is missing or misspelled, this fails immediately at startup with a
clear message, rather than halfway through someone's first question.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py -> backend/app -> backend -> project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    """Every setting the backend needs. Names must match the .env keys."""

    # --- database ---
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str
    db_name: str = "foodiequery"

    # A second, restricted MySQL account that is only allowed to SELECT.
    # The API uses this one. Even if a bad query slipped past our checks,
    # MySQL itself would refuse to run it.
    db_ro_user: str = ""
    db_ro_password: str = ""

    # --- Groq (the free LLM provider) ---
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-120b"

    # --- safety limits ---
    max_rows_returned: int = 200        # hard cap glued onto every query
    query_timeout_seconds: int = 20
    rate_limit: str = "15/minute"       # per visitor, per endpoint

    # --- frontend ---
    # Which web addresses are allowed to call this API from a browser.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",          # ignore .env keys we do not declare here
        case_sensitive=False,
    )

    @property
    def read_user(self) -> str:
        """The restricted account if it exists, otherwise fall back to root."""
        return self.db_ro_user or self.db_user

    @property
    def read_password(self) -> str:
        return self.db_ro_password or self.db_password

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """
    Reads the .env file once and reuses the result.

    lru_cache is Python's built-in memo: the first call does the work, every
    later call gets the same object back instantly.
    """
    return Settings()
