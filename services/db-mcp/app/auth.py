"""Bearer-token authentication boundary for this MCP server.

Every MCP server is a separate trust boundary (see project security
spec): it must authenticate its caller rather than relying on network
placement alone. The FastAPI backend is the only intended caller; it
sends `Authorization: Bearer <token>` on every request to `/mcp`.

This middleware is applied ONLY to the `/mcp` mount (see `server.py`),
not to `/health`, so health checks remain usable by orchestrators
(Docker/Kubernetes) without needing the service credential.

Implemented as raw ASGI (not Starlette's `BaseHTTPMiddleware`).
Streamable HTTP uses a streaming SSE response; `BaseHTTPMiddleware`
buffers that channel and breaks MCP initialize / tool calls.
"""

from __future__ import annotations

import logging

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)


class BearerAuthMiddleware:
    """Rejects any request without a matching `Authorization: Bearer` header.

    Never logs the token itself (matches or not) — only the fact that a
    request was rejected, plus the path, so failures are debuggable
    without leaking credential material into logs.
    """

    def __init__(self, app: ASGIApp, expected_token: str) -> None:
        self.app = app
        self._expected_token = expected_token

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        header = ""
        for key, value in scope.get("headers") or []:
            if key == b"authorization":
                header = value.decode("latin-1")
                break

        provided = header[7:].strip() if header.lower().startswith("bearer ") else None

        if provided is None or provided != self._expected_token:
            path = scope.get("path", "")
            logger.warning(
                "unauthorized_mcp_request",
                extra={"event": "unauthorized_mcp_request", "path": path},
            )
            response = JSONResponse({"error": "unauthorized"}, status_code=401)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
