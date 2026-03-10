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

    # --- LLM (optional, for AIOps suggestion) ---
    llm_provider: str = Field(
        default="none",
        alias="AT_LLM_PROVIDER",
        description="'openai-compatible' or 'none'. When set, enables AI suggestion on alerts.",
    )
    llm_api_base: str = Field(
        default="https://api.openai.com/v1",
        alias="AT_LLM_API_BASE",
        description="OpenAI-compatible API base URL (e.g., Anthropic, Ollama).",
    )
    llm_api_key: str = Field(
        default="",
        alias="AT_LLM_API_KEY",
        description="API key for the LLM provider.",
    )
    llm_model: str = Field(
        default="gpt-4o-mini",
        alias="AT_LLM_MODEL",
        description="Model name for the LLM provider.",
    )

    # --- Admin ---
    admin_users: str = Field(
        default="",
        alias="AT_ADMIN_USERS",
        description="Comma-separated list of usernames allowed to access admin endpoints. Empty = all authenticated users.",
    )

    # --- Security toggles ---
    openapi_enabled: bool = Field(
        default=True,
        alias="AT_OPENAPI_ENABLED",
        description="Expose /docs and /openapi.json. Disable in production.",
    )

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

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider != "none" and bool(self.llm_api_key)


_BLOCKED_HOSTS = frozenset({
    "169.254.169.254",   # AWS/GCP metadata
    "metadata.google.internal",
    "100.100.100.200",   # Alibaba metadata
})


def validate_cluster_url(url: str, field_name: str = "url") -> str:
    """Validate a cluster URL is safe (no SSRF to internal metadata endpoints)."""
    if not url:
        return url
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid {field_name}: only http/https schemes are allowed")
    hostname = (parsed.hostname or "").lower()
    if hostname in _BLOCKED_HOSTS:
        raise ValueError(f"Invalid {field_name}: blocked host '{hostname}'")
    # Block link-local / loopback ranges for metadata services
    if hostname.startswith("169.254.") or hostname == "[::ffff:169.254.169.254]":
        raise ValueError(f"Invalid {field_name}: link-local addresses are blocked")
    return url


def load_clusters_config(config_dir: str) -> list[dict]:
    """Load cluster definitions from clusters.yaml with URL validation."""
    config_path = Path(config_dir) / "clusters.yaml"
    if not config_path.exists():
        return []
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not data or "clusters" not in data:
        return []
    clusters = data["clusters"]
    for cdef in clusters:
        name = cdef.get("name", "unknown")
        for url_field in ("prometheus_url", "alertmanager_url"):
            if url_field in cdef:
                validate_cluster_url(cdef[url_field], f"{name}.{url_field}")
    return clusters


# Singleton
settings = Settings()
