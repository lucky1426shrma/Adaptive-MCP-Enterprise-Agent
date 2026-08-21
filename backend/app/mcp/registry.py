"""Holds the backend's MCP client instances — one per configured remote
MCP server (RAG, DB, and later GitHub).

Built once at application startup (`initialize_registry`, called from
`main.py`'s lifespan) and reused for the process lifetime.
`MCPServerClient` opens a fresh session per call (see client.py), so
sharing one instance per server across concurrent requests is safe —
there's no shared connection state to race on.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from app.config import Settings
from app.mcp.client import MCPServerClient

logger = logging.getLogger(__name__)


class MCPRegistry:
    def __init__(self) -> None:
        self._clients: Dict[str, MCPServerClient] = {}

    def register(self, name: str, client: MCPServerClient) -> None:
        self._clients[name] = client

    def get(self, name: str) -> Optional[MCPServerClient]:
        return self._clients.get(name)

    def all(self) -> Dict[str, MCPServerClient]:
        return dict(self._clients)


# Process-wide singleton, populated by initialize_registry() at startup.
registry = MCPRegistry()


def initialize_registry(settings: Settings) -> None:
    if settings.rag_mcp_url:
        registry.register(
            "rag",
            MCPServerClient(
                name="rag",
                url=settings.rag_mcp_url,
                auth_token=settings.rag_mcp_auth_token,
                timeout_seconds=settings.mcp_timeout_seconds,
            ),
        )
        logger.info("mcp_client_registered", extra={"event": "mcp_client_registered", "server": "rag"})
    else:
        logger.warning("rag_mcp_not_configured", extra={"event": "rag_mcp_not_configured"})

    if settings.db_mcp_url:
        registry.register(
            "db",
            MCPServerClient(
                name="db",
                url=settings.db_mcp_url,
                auth_token=settings.db_mcp_auth_token,
                timeout_seconds=settings.mcp_timeout_seconds,
            ),
        )
        logger.info("mcp_client_registered", extra={"event": "mcp_client_registered", "server": "db"})
    else:
        logger.warning("db_mcp_not_configured", extra={"event": "db_mcp_not_configured"})

    if settings.github_mcp_url:
        registry.register(
            "github",
            MCPServerClient(
                name="github",
                url=settings.github_mcp_url,
                auth_token=settings.github_mcp_auth_token,
                timeout_seconds=settings.mcp_timeout_seconds,
            ),
        )
        logger.info("mcp_client_registered", extra={"event": "mcp_client_registered", "server": "github"})
    else:
        logger.warning("github_mcp_not_configured", extra={"event": "github_mcp_not_configured"})
