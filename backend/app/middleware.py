"""ASGI middleware for request correlation IDs, request-level logging,
and (Phase 10) the root tracing span for every request.

Every request gets: a stable `request_id` that shows up in every log
line the request produces and is echoed back via `X-Request-ID`
(since Phase 1); AND, as of Phase 10, a real OpenTelemetry span
("http.request") that every downstream span — MCP calls, LLM calls,
agent graph nodes, retrieval sub-steps — nests underneath, giving one
end-to-end trace per request. `request_id` and the OTel trace ID are
DELIBERATELY KEPT SEPARATE (not merged into one ID): `request_id` works
with zero dependencies and always exists; the OTel trace ID only
exists when `opentelemetry` is installed and tracing is configured.
`TraceContextFilter` (see `app/observability/log_correlation.py`)
attaches the OTel trace/span ID to log records too, so a log line can
be correlated to both.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import request_id_var
from app.observability.span_helper import start_span

logger = logging.getLogger("app.request")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assigns a correlation ID and root trace span to each request, and
    logs start/end events."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        start = time.perf_counter()

        logger.info(
            "request_started",
            extra={
                "event": "request_started",
                "method": request.method,
                "path": request.url.path,
            },
        )

        with start_span(
            "http.request",
            {
                "http.method": request.method,
                "http.path": request.url.path,
                "request_id": request_id,
            },
        ):
            try:
                response = await call_next(request)
            except Exception:
                logger.exception(
                    "request_failed",
                    extra={
                        "event": "request_failed",
                        "method": request.method,
                        "path": request.url.path,
                    },
                )
                request_id_var.reset(token)
                raise

        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request_completed",
            extra={
                "event": "request_completed",
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": duration_ms,
            },
        )

        request_id_var.reset(token)
        return response
