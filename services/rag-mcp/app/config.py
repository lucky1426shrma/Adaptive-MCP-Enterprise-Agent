"""Centralized configuration for the RAG MCP server.

Env var names here are local to this service (its own `.env`), separate
from how the FastAPI backend refers to this service in *its* `.env`
(`RAG_MCP_URL`, `RAG_MCP_AUTH_TOKEN`) — each service owns its own
configuration namespace, consistent with independent deployability.
`AUTH_TOKEN` here must be set to the same value as `RAG_MCP_AUTH_TOKEN`
on the backend.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_DEFAULT_TOKEN = "dev-local-only-change-me"  # noqa: S105 - intentional, checked against at runtime


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    service_name: str = "rag-mcp"
    environment: str = "development"  # development | staging | production
    host: str = "0.0.0.0"
    port: int = 8001

    log_level: str = "INFO"
    log_format: str = "json"

    # Trust boundary between this server and its only intended caller
    # (the FastAPI backend). See app/auth.py.
    auth_token: str = _DEV_DEFAULT_TOKEN

    # --- Embedding / reranking models (local, free, open-source) ---
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    enable_reranker: bool = True

    # --- Qdrant ---
    # If `qdrant_url` is set, connect to a remote/self-hosted Qdrant
    # server. Otherwise fall back to local on-disk Qdrant at
    # `qdrant_local_path` (no server process required) — useful for
    # local development without Docker.
    qdrant_url: Optional[str] = None
    qdrant_local_path: Optional[str] = "./data/qdrant_local"
    qdrant_collection: str = "rag_chunks"

    # --- BM25 corpus source (written by scripts/ingest.py) ---
    chunks_index_path: Path = Path("./data/index/chunks.jsonl")

    # --- Retrieval pipeline tuning ---
    dense_k: int = 20
    sparse_k: int = 20
    rerank_pool_size: int = 15
    rrf_k: int = 60

    # --- Observability (Phase 10) ---
    otel_exporter_otlp_endpoint: Optional[str] = None

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_runtime(self) -> None:
        """Fail closed rather than silently running an unauthenticated
        MCP server outside of local development."""
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
