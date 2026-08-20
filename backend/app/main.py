"""FastAPI application entrypoint.

This is the FastAPI backend referenced throughout the project as the
MCP client / agent orchestrator: MCP client layer (Phase 4-6), LangGraph
agent over OpenRouter (Phase 7-8), and security hardening (Phase 9) —
rate limiting, an optional backend API key, tightened CORS, and a
global exception handler — are all wired in here.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.service import AgentService, set_agent_service
from app.api.chat import router as chat_router
from app.api.db_tools import router as db_tools_router
from app.api.github_tools import router as github_tools_router
from app.api.health import router as health_router
from app.api.rag_tools import router as rag_tools_router
from app.config import get_settings
from app.llm.model_validation import ModelValidationError, validate_model_is_free
from app.llm.openrouter_provider import OpenRouterProvider
from app.logging_config import configure_logging
from app.mcp.registry import initialize_registry, registry
from app.middleware import RequestContextMiddleware
from app.observability.tracing import configure_tracing
from app.security.api_key_middleware import BackendAPIKeyMiddleware
from app.security.rate_limit_middleware import RateLimitMiddleware
from app.security.rate_limiter import RateLimiter

settings = get_settings()
configure_logging(log_level=settings.log_level, log_format=settings.log_format)
configure_tracing(
    service_name=settings.otel_service_name,
    service_version=settings.app_version,
    otlp_endpoint=settings.otel_exporter_otlp_endpoint,
)

logger = logging.getLogger(__name__)

# Held at module scope so lifespan's startup and shutdown blocks can
# both reach it (to close the httpx client cleanly on shutdown).
_llm_provider: OpenRouterProvider | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application startup/shutdown hooks.

    Builds the MCP client registry, then — if OPENROUTER_API_KEY and
    OPENROUTER_MODEL are both set — validates the configured model is
    confirmed free (fails startup outright if not: this specific
    zero-cost guarantee is treated as non-negotiable, unlike an
    unconfigured MCP server, which just disables one capability) and
    builds the agent. If neither is set, the agent is left unavailable
    and POST /chat returns 503, while everything else still runs.
    """
    global _llm_provider

    logger.info(
        "application_startup",
        extra={
            "event": "application_startup",
            "environment": settings.environment,
            "version": settings.app_version,
        },
    )
    initialize_registry(settings)

    if settings.openrouter_api_key and settings.openrouter_model:
        try:
            await validate_model_is_free(
                settings.openrouter_model,
                api_key=settings.openrouter_api_key,
                base_url=settings.openrouter_base_url,
            )
        except ModelValidationError as exc:
            if settings.openrouter_model.endswith(":free"):
                logger.warning(
                    "openrouter_model_validation_warning",
                    extra={"event": "openrouter_model_validation_warning", "warning": str(exc)},
                )
            else:
                logger.error(
                    "openrouter_model_validation_failed",
                    extra={"event": "openrouter_model_validation_failed", "error": str(exc)},
                )
                raise RuntimeError(str(exc)) from exc

        _llm_provider = OpenRouterProvider(
            api_key=settings.openrouter_api_key,
            model=settings.openrouter_model,
            base_url=settings.openrouter_base_url,
            timeout_seconds=settings.openrouter_timeout_seconds,
        )
        agent_service = AgentService(
            llm_provider=_llm_provider,
            registry=registry,
            max_tool_iterations=settings.llm_max_tool_iterations,
            agent_timeout_seconds=settings.agent_timeout_seconds,
            rag_max_retrieval_attempts=settings.rag_max_retrieval_attempts,
        )
        set_agent_service(agent_service)
        logger.info("agent_service_initialized", extra={"event": "agent_service_initialized"})
    else:
        logger.warning("openrouter_not_configured", extra={"event": "openrouter_not_configured"})
        set_agent_service(None)

    yield

    set_agent_service(None)
    if _llm_provider is not None:
        await _llm_provider.aclose()
    logger.info("application_shutdown", extra={"event": "application_shutdown"})


def create_app() -> FastAPI:
    """Application factory.

    Building the app via a factory (instead of a bare module-level
    `FastAPI()` singleton) keeps construction explicit and makes it easy
    for tests to build isolated app instances later if needed.
    """
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Adaptive MCP Enterprise Agent — backend API. FastAPI + "
            "LangGraph orchestrator and MCP client for RAG / Database / "
            "GitHub capabilities exposed via independent MCP servers."
        ),
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        # Tightened from "*" (Phase 9): only what the frontend actually
        # needs. Widen deliberately if a real client requires more,
        # rather than defaulting back to a wildcard.
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.add_middleware(
        BackendAPIKeyMiddleware, expected_key=settings.backend_api_key or None
    )
    application.add_middleware(
        RateLimitMiddleware,
        limiter=RateLimiter(
            max_requests=settings.rate_limit_max_requests,
            window_seconds=settings.rate_limit_window_seconds,
        ),
        trust_proxy_headers=settings.trust_proxy_headers,
    )
    # Registered last so it wraps every request/response Starlette
    # processes (middleware runs outside-in on the way in, inside-out
    # on the way out) — added last = outermost = runs FIRST, so every
    # request gets a correlation ID before CORS/rate-limit/auth even
    # run, including ones that get rejected by them.
    #
    # Ordering of the three above matters for correctness, not just
    # style: CORS must run before the rate limiter and API-key check so
    # browser CORS preflight (OPTIONS) requests — which never carry the
    # app's Authorization header — get handled by CORSMiddleware itself
    # rather than being rejected as unauthorized/rate-limited first.
    application.add_middleware(RequestContextMiddleware)

    @application.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Safety net for anything not already caught by a route's own
        try/except (see app/api/mcp_helpers.py for the deliberate,
        per-error-type handling most routes rely on). Full detail is
        logged server-side with the request's correlation ID; only a
        generic message reaches the caller.
        """
        logger.exception(
            "unhandled_exception",
            extra={"event": "unhandled_exception", "path": request.url.path},
        )
        return JSONResponse({"detail": "Internal server error."}, status_code=500)

    application.include_router(health_router)
    application.include_router(chat_router)
    application.include_router(rag_tools_router)
    application.include_router(db_tools_router)
    application.include_router(github_tools_router)

    return application


app = create_app()
