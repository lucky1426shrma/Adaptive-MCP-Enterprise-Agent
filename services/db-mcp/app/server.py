"""DB MCP server entrypoint — Phase 5: real PostgreSQL backing.

Exposes one tool, `get_payment_failure_stats`, now backed by a real,
read-only, parameterized query (see `app/database.py`) against a
`db_mcp_reader` role that only has SELECT privileges (see
`db/setup_and_seed.py`). The tool name and input contract are unchanged
from the Phase 2 stub — only the implementation behind it changed.

See `services/rag-mcp/app/server.py` for the detailed explanation of
the FastMCP/Streamable-HTTP mounting pattern used here.
"""


import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.auth import BearerAuthMiddleware
from app.config import get_settings
from app.database import Database
from app.logging_config import configure_logging
from app.schemas import PaymentFailureStatsInput
from app.span_helper import start_span
from app.tracing import configure_tracing

settings = get_settings()
configure_logging(log_level=settings.log_level, log_format=settings.log_format)
configure_tracing(
    service_name=settings.service_name, service_version="0.1.0", otlp_endpoint=settings.otel_exporter_otlp_endpoint
)
logger = logging.getLogger(__name__)

mcp_server = FastMCP(name=settings.service_name)

database = Database(
    dsn=settings.database_url,
    min_size=settings.pool_min_size,
    max_size=settings.pool_max_size,
    query_timeout_seconds=settings.query_timeout_seconds,
)


@mcp_server.tool()
async def get_payment_failure_stats(
    start_date: str, end_date: str, service: str | None = None
) -> Dict[str, Any]:
    """Get payment failure statistics for a date range.

    Returns aggregate attempt/failure counts for the given inclusive
    date range (UTC), optionally filtered to one service. Date range is
    limited to 90 days to bound query cost. Runs a read-only,
    parameterized, timeout-bounded query against a database role that
    only has SELECT privileges.
    """
    with start_span("db.get_payment_failure_stats_tool", {"start_date": start_date, "end_date": end_date}):
        validated = PaymentFailureStatsInput(start_date=start_date, end_date=end_date, service=service)

        logger.info(
            "get_payment_failure_stats_called",
            extra={
                "event": "get_payment_failure_stats_called",
                "start_date": validated.start_date,
                "end_date": validated.end_date,
                "service": validated.service,
            },
        )

        try:
            return await database.get_payment_failure_stats(
                validated.start_date, validated.end_date, validated.service
            )
        except Exception:
            logger.exception(
                "get_payment_failure_stats_query_failed",
                extra={"event": "get_payment_failure_stats_query_failed"},
            )
            # Sanitized error surfaced to the caller (never leak the raw DB
            # exception, which could include connection details).
            return {
                "start_date": validated.start_date,
                "end_date": validated.end_date,
                "service": validated.service,
                "error": "Failed to query payment failure statistics.",
            }


mcp_asgi_app = mcp_server.streamable_http_app()


async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "service": settings.service_name, "environment": settings.environment}
    )


async def readiness(request: Request) -> JSONResponse:
    db_ok = await database.ping()
    if db_ok:
        return JSONResponse({"status": "ok", "service": settings.service_name, "database": "ok"})
    return JSONResponse(
        {"status": "not_ready", "service": settings.service_name, "database": "unreachable"},
        status_code=503,
    )


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    async with mcp_asgi_app.router.lifespan_context(mcp_asgi_app):
        logger.info("db_mcp_startup", extra={"event": "db_mcp_startup"})
        await database.connect()
        yield
        await database.disconnect()
        logger.info("db_mcp_shutdown", extra={"event": "db_mcp_shutdown"})


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/health/ready", readiness, methods=["GET"]),
        Mount(
            "",
            app=mcp_asgi_app,
            middleware=[Middleware(BearerAuthMiddleware, expected_token=settings.auth_token)],
        ),
    ],
    lifespan=lifespan,
)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
