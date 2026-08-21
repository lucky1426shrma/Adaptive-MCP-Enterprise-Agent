"""Liveness and readiness endpoints.

- `/health`       — liveness: is the process up and able to handle HTTP?
- `/health/ready` — readiness: is the process able to serve *real*
  requests right now? As of Phase 4/5 this checks connectivity to every
  MCP server currently registered (RAG, DB) via a fast, short-timeout
  `list_tools()` call — NOT a full tool invocation, just a protocol
  round-trip — so an orchestrator doesn't route traffic to a backend
  instance that can't actually reach its MCP servers.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.mcp.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

# Readiness checks use their own short timeout, independent of
# mcp_timeout_seconds (which governs real tool calls) — a readiness
# probe should fail fast, not wait 30s per dependency.
_READINESS_CHECK_TIMEOUT_SECONDS = 3.0


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    dependencies: Dict[str, str]


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
async def liveness() -> HealthResponse:
    """Report that the process is running. No dependency checks here —
    keep this cheap even after readiness grows more dependencies."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )


@router.get(
    "/health/ready", response_model=ReadinessResponse, summary="Readiness check"
)
async def readiness() -> ReadinessResponse:
    """Report readiness to serve real traffic.

    Only servers currently registered (i.e. configured via
    RAG_MCP_URL / DB_MCP_URL) are checked; an unconfigured server isn't
    treated as a failure — some deployments may intentionally run with
    a subset of MCP servers available.
    """
    settings = get_settings()
    dependencies: Dict[str, str] = {}
    all_ok = True

    for name, client in registry.all().items():
        try:
            async with asyncio.timeout(_READINESS_CHECK_TIMEOUT_SECONDS):
                await client.list_tools()
            dependencies[f"mcp_{name}"] = "ok"
        except Exception:  # noqa: BLE001 - readiness must never raise, only report
            logger.warning(
                "readiness_check_failed",
                extra={"event": "readiness_check_failed", "server": name},
            )
            dependencies[f"mcp_{name}"] = "unreachable"
            all_ok = False

    return ReadinessResponse(
        status="ok" if all_ok else "degraded",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        dependencies=dependencies,
    )

