"""Application configuration — reads env vars (AT_* prefix) and clusters.yaml."""

import os
from enum import Enum
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import yaml
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class AuthMode(str, Enum):
    """Supported authentication modes."""
    NONE = "none"
    OAUTH2_PROXY = "oauth2-proxy"


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    # --- Database ---
    database_url: str = Field(
        default="",
        alias="AT_DATABASE_URL",
        description="Empty = SQLite (/data/alerts.db), otherwise MariaDB connection string",
    )

    # --- Auth ---
    auth_mode: AuthMode = Field(
        default=AuthMode.NONE,
        alias="AT_AUTH_MODE",
        description="'oauth2-proxy' or 'none'",
    )

    # --- Poller ---
    poller_interval_hours: int = Field(default=8, ge=1, alias="AT_POLLER_INTERVAL_HOURS")
    poller_lookback_hours: int = Field(default=12, ge=1, alias="AT_POLLER_LOOKBACK_HOURS")

    # --- Timeouts (seconds) ---
    pull_timeout: float = Field(default=30.0, alias="AT_PULL_TIMEOUT_SECONDS")
    health_check_timeout: float = Field(default=10.0, alias="AT_HEALTH_CHECK_TIMEOUT_SECONDS")

    # --- Retention ---
    retention_months: int = Field(default=12, alias="AT_RETENTION_MONTHS")
    purge_cron: str = Field(default="0 3 1 * *", alias="AT_PURGE_CRON")

    # --- Timezone ---
    display_timezone: str = Field(
        default="Asia/Taipei",
        alias="AT_DISPLAY_TIMEZONE",
        description="IANA timezone for UI display and shift-report week boundaries. DB always stores UTC.",
    )

    @field_validator("display_timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate that the timezone string is a valid IANA timezone."""
        try:
            ZoneInfo(v)
        except (KeyError, Exception) as e:
            raise ValueError(f"Invalid IANA timezone '{v}': {e}") from e
        return v

    # --- Paths ---
    data_dir: str = Field(default="/data", alias="AT_DATA_DIR")
    config_dir: str = Field(default="/app/config", alias="AT_CONFIG_DIR")

    model_config = {"populate_by_name": True}

    @property
    def effective_database_url(self) -> str:
        """Return SQLite URL if DATABASE_URL is empty.

        Note: does NOT create directories — that is init_db()'s job.
        Avoids PermissionError when config is imported in CI / tests.
        """
        if self.database_url:
            return self.database_url
        db_path = Path(self.data_dir) / "alerts.db"
        return f"sqlite:///{db_path}"

    @property
    def is_sqlite(self) -> bool:
        return self.effective_database_url.startswith("sqlite")


def load_clusters_config(config_dir: str) -> list[dict]:
    """Load cluster definitions from clusters.yaml."""
    config_path = Path(config_dir) / "clusters.yaml"
    if not config_path.exists():
        return []
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "clusters" not in data:
        return []
    return data["clusters"]


# Singleton
settings = Settings()
