"""Centralized configuration for the GitHub MCP server.

Phase 2 scope: skeleton proving the pattern with a stub tool. Real
GitHub API integration (auth, repository scoping, real commit/issue
search) is Phase 6.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_DEFAULT_TOKEN = "dev-local-only-change-me"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    service_name: str = "github-mcp"
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8003

    log_level: str = "INFO"
    log_format: str = "json"

    auth_token: str = _DEV_DEFAULT_TOKEN

    # Reserved for Phase 6 — not read yet. A least-privilege, read-only
    # PAT used BY this server; never exposed to the LLM or the backend.
    github_token: str = ""

    github_api_base_url: str = "https://api.github.com"
    github_api_timeout_seconds: float = 10.0

    # Least-privilege repository scoping: even once real GitHub API
    # calls exist, this server should only ever be able to touch
    # repositories explicitly listed here, not arbitrary ones the LLM
    # asks about. Empty list = deny everything (fail closed).
    allowed_repositories: List[str] | str = Field(default_factory=list)

    # --- Observability (Phase 10) ---
    otel_exporter_otlp_endpoint: Optional[str] = None

    @field_validator("allowed_repositories", mode="after")
    @classmethod
    def _split_csv(cls, value: List[str] | str) -> List[str]:
        if isinstance(value, str):
            val = value.strip()
            if val.startswith("[") and val.endswith("]"):
                import json
                try:
                    parsed = json.loads(val)
                    if isinstance(parsed, list):
                        return [str(x).strip() for x in parsed if str(x).strip()]
                except Exception:
                    pass
            return [repo.strip() for repo in val.split(",") if repo.strip()]
        return list(value)

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
