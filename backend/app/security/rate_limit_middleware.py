"""ASGI middleware applying `RateLimiter` per client key.

Exempts `/health` and `/health/ready` so orchestrators (Docker/K8s
liveness/readiness probes) can poll freely without being throttled.

Client key is the connecting IP by default. If `trust_proxy_headers` is
enabled, the first entry of `X-Forwarded-For` is used instead — only
enable this behind a reverse proxy that itself sets/overwrites that
header, never directly on the public internet, since `X-Forwarded-For`
is trivially spoofable by any client when nothing trusted is rewriting
it.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from app.security.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

_EXEMPT_PATHS = {"/health", "/health/ready"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, limiter: RateLimiter, trust_proxy_headers: bool = False) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._trust_proxy_headers = trust_proxy_headers

    def _client_key(self, request: Request) -> str:
        if self._trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for")
            if forwarded:
                return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        key = self._client_key(request)
        if not self._limiter.allow(key):
            retry_after = self._limiter.retry_after_seconds(key)
            logger.warning(
                "rate_limit_exceeded",
                extra={"event": "rate_limit_exceeded", "client": key, "path": request.url.path},
            )
            return JSONResponse(
                {"detail": "Rate limit exceeded. Please slow down."},
                status_code=429,
                headers={"Retry-After": str(int(retry_after) + 1)},
            )

        return await call_next(request)
