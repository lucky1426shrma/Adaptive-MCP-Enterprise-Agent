"""Optional API-key gate for the backend's own public-facing endpoints —
distinct from the internal bearer tokens the backend uses to call each
MCP server (`RAG_MCP_AUTH_TOKEN` etc., see `app/mcp/client.py`), which
protect a completely different boundary (backend -> MCP server).

If `BACKEND_API_KEY` is unset, this middleware is a no-op (open access)
— appropriate for pure local development, matching every other
"unconfigured means disabled, not crashed" pattern in this project.
Setting it requires every non-exempt request to carry
`Authorization: Bearer <key>`.

HONEST SCOPE: this is a single shared application-level key, not a
per-user authentication system. A real multi-user deployment should
replace this with proper user authentication (OAuth/OIDC, session
tokens, etc.) — this is documented as a known limitation in
`docs/security.md`, not presented as a complete solution.
"""

from __future__ import annotations

import logging
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/health", "/health/ready"}


class BackendAPIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, expected_key: Optional[str]) -> None:
        super().__init__(app)
        self._expected_key = expected_key or None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS" or self._expected_key is None or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        header = request.headers.get("authorization", "")
        provided = header[7:].strip() if header.lower().startswith("bearer ") else None

        if provided is None or provided != self._expected_key:
            logger.warning(
                "unauthorized_backend_request",
                extra={"event": "unauthorized_backend_request", "path": request.url.path},
            )
            return JSONResponse({"detail": "unauthorized"}, status_code=401)

        return await call_next(request)
