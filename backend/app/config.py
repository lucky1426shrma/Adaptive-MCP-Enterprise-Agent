"""Centralized application configuration.

All configuration is sourced from environment variables (or a `.env` file
in local development). Nothing in this codebase should hard-code secrets,
model IDs, service URLs, or environment-specific values outside of this
module — later phases (OpenRouter, RAG MCP, DB MCP, GitHub MCP, Qdrant,
observability) will extend `Settings` rather than reading `os.environ`
directly elsewhere.
"""

from __future__ import annotations

from functools import lru_cache
from typing import List , Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, validated once at process startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application metadata ---
    app_name: str = "adaptive-mcp-enterprise-agent"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")  # development | staging | production

    # --- Server ---
    host: str = "0.0.0.0"
    port: int = 8000

    # --- Logging ---
    log_level: str = "INFO"
    log_format: str = "json"  # json | console

    # --- CORS ---
    # The frontend is the only expected browser-facing caller. MCP servers
    # are never called from the browser (see security model) so they are
    # not part of this allowlist.
    cors_allowed_origins: List[str] | str = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )

    # --- MCP servers (Phase 4: RAG; Phase 5: DB) ---
    # A None url means "not configured" — the registry simply won't
    # register a client for that server, and any route depending on it
    # returns 503 rather than the app failing to start. This lets the
    # backend run with a subset of MCP servers available during
    # incremental development.
    rag_mcp_url: Optional[str] = None
    rag_mcp_auth_token: str = ""

    db_mcp_url: Optional[str] = None
    db_mcp_auth_token: str = ""

    github_mcp_url: Optional[str] = None
    github_mcp_auth_token: str = ""

    # Applied per MCP call (list_tools / call_tool), not per HTTP request.
    mcp_timeout_seconds: float = 30.0

    # --- LLM provider (Phase 7): OpenRouter is the ONLY LLM provider ---
    # Both must be set for the agent to activate; unset means the agent
    # is unavailable (POST /chat returns 503) but the rest of the app
    # still runs — same "run with a subset configured" philosophy as
    # the MCP servers above.
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_timeout_seconds: float = 90.0

    # --- Agent behavior ---
    # Caps LLM turns per request (not raw tool calls — one LLM turn can
    # request multiple tool calls at once). This is the graph's explicit
    # stopping criterion; see app/agent/nodes.py's should_continue().
    llm_max_tool_iterations: int = 6
    # Wall-clock cap for one full agent run (all LLM + tool round trips
    # combined), independent of mcp_timeout_seconds / openrouter_timeout_seconds
    # which bound individual calls.
    agent_timeout_seconds: float = 120.0

    # --- Agentic RAG (Phase 8) ---
    # Caps rag__search_knowledge calls specifically, independent of
    # llm_max_tool_iterations (which caps LLM turns overall — a
    # question needing DB + GitHub + RAG shouldn't have its non-RAG
    # tool calls squeezed out by a shared budget). See
    # app/agent/rag_loop_guard.py.
    rag_max_retrieval_attempts: int = 3

    # --- Security (Phase 9) ---
    # Optional shared application-level key gating the backend's own
    # public endpoints. Empty = disabled (open access), matching the
    # "unconfigured means disabled" pattern used throughout this
    # project. See app/security/api_key_middleware.py for the honest
    # scope note (single shared key, not per-user auth).
    backend_api_key: str = ""

    # In-memory, single-process rate limiting (see
    # app/security/rate_limiter.py for the multi-replica limitation).
    # Default is generous enough that a full local `pytest` run (which
    # shares this same module-level `app` instance, and therefore this
    # same limiter's budget, across every test file) doesn't trip it —
    # if you add many more tests that call the API directly, either
    # raise this default or give the rate-limited routes their own
    # per-test app instance with a fresh limiter.
    rate_limit_max_requests: int = 60
    rate_limit_window_seconds: float = 60.0

    # Only enable behind a reverse proxy that itself sets/overwrites
    # X-Forwarded-For — never on the open internet, since that header
    # is trivially spoofable otherwise.
    trust_proxy_headers: bool = False

    # --- Observability (Phase 10) ---
    # Unset means spans are created but never exported anywhere (see
    # app/observability/tracing.py) — not a requirement to run this
    # project, per the spec's "no mandatory external observability
    # dependency" rule.
    otel_exporter_otlp_endpoint: Optional[str] = None
    otel_service_name: str = "adaptive-mcp-enterprise-agent-backend"

    @field_validator("cors_allowed_origins", mode="after")
    @classmethod
    def _split_csv_origins(cls, value: List[str] | str) -> List[str]:
        """Allow CORS_ALLOWED_ORIGINS to be a comma-separated env string or list."""
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
            return [origin.strip() for origin in val.split(",") if origin.strip()]
        return list(value)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached Settings instance.

    Cached (rather than re-instantiated per call) so environment parsing
    and validation happens once per process. Use `get_settings.cache_clear()`
    in tests if you need to re-read the environment mid-run.
    """
    return Settings()
