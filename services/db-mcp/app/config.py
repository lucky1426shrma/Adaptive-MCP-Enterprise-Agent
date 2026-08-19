"""Centralized configuration for the DB MCP server.

Phase 2 scope: this service is a skeleton — it proves the Streamable
HTTP + auth + validated-tool pattern with a stub tool. Real PostgreSQL
connectivity, schema, and safe query execution are Phase 5.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_DEFAULT_TOKEN = "dev-local-only-change-me"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    service_name: str = "db-mcp"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8002

    log_level: str = "INFO"
    log_format: str = "json"

    auth_token: str = _DEV_DEFAULT_TOKEN

    # Read-only connection string for the `db_mcp_reader` role (see
    # db/setup_and_seed.py). This is the ONLY Postgres credential this
    # running server ever holds — least privilege by construction, not
    # just convention: the reader role has SELECT-only grants.
    database_url: str = ""

    query_timeout_seconds: float = 5.0
    pool_min_size: int = 1
    pool_max_size: int = 5

    # Safety limit, enforced in app/schemas.py's input validation.
    max_date_range_days: int = 90

    # --- Observability (Phase 10) ---
    otel_exporter_otlp_endpoint: Optional[str] = None

    def validate_runtime(self) -> None:
        if self.environment.lower() != "development" and self.auth_token == _DEV_DEFAULT_TOKEN:
            raise RuntimeError(
                "AUTH_TOKEN is still the insecure development default. "
                "Set AUTH_TOKEN to a real secret for non-development environments."
            )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime()
    return settings
