"""GitHub MCP server entrypoint — Phase 6: real GitHub API integration.

Exposes one tool, `search_recent_commits`, now backed by real GitHub
REST API calls instead of the Phase 2 stub. Enforces repository
allow-listing server-side (`app/repo_scope.py`) — the repository the
caller requests is a suggestion, not a grant; this server decides what
is actually queryable, independent of what an LLM-driven caller asks
for.

See `services/rag-mcp/app/server.py` for the detailed explanation of
the FastMCP/Streamable-HTTP mounting pattern used here.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from app.auth import BearerAuthMiddleware
from app.commit_shaping import shape_commit
from app.config import get_settings
from app.github_client import GitHubClient
from app.github_exceptions import (
    GitHubAPIError,
    GitHubAuthError,
    GitHubNotFoundError,
    GitHubRateLimitError,
)
from app.logging_config import configure_logging
from app.repo_scope import is_repository_allowed
from app.schemas import SearchRecentCommitsInput
from app.span_helper import start_span
from app.tracing import configure_tracing

settings = get_settings()
configure_logging(log_level=settings.log_level, log_format=settings.log_format)
configure_tracing(
    service_name=settings.service_name, service_version="0.1.0", otlp_endpoint=settings.otel_exporter_otlp_endpoint
)
logger = logging.getLogger(__name__)

mcp_server = FastMCP(name=settings.service_name)

# Populated at startup if GITHUB_TOKEN is configured (see lifespan
# below). None means "not configured" — the tool reports that clearly
# rather than the server failing to start, consistent with how the
# backend's MCP registry treats an unconfigured MCP server (Phase 4).
github_client: Optional[GitHubClient] = None


def _error_result(validated: SearchRecentCommitsInput, message: str) -> Dict[str, Any]:
    return {
        "repository": validated.repository,
        "since": validated.since,
        "path_filter": validated.path_filter,
        "commits": [],
        "error": message,
    }


@mcp_server.tool()
async def search_recent_commits(
    repository: str, since: str, path_filter: Optional[str] = None, max_results: int = 10
) -> Dict[str, Any]:
    """Search recent commits in a repository.

    Returns up to `max_results` commits on or after `since` (ISO date),
    optionally filtered to a path prefix, newest first. Only
    repositories explicitly configured in this server's allow-list can
    be queried — requesting any other repository returns a clear error
    rather than data, regardless of what the caller asks for.
    """
    validated = SearchRecentCommitsInput(
        repository=repository, since=since, path_filter=path_filter, max_results=max_results
    )

    with start_span("github.search_recent_commits_tool", {"repository": validated.repository}):
        logger.info(
            "search_recent_commits_called",
            extra={
                "event": "search_recent_commits_called",
                "repository": validated.repository,
                "since": validated.since,
                "path_filter": validated.path_filter,
                "max_results": validated.max_results,
            },
        )

        if not is_repository_allowed(validated.repository, settings.allowed_repositories):
            logger.warning(
                "search_recent_commits_repository_not_allowed",
                extra={
                    "event": "search_recent_commits_repository_not_allowed",
                    "repository": validated.repository,
                },
            )
            return _error_result(
                validated,
                f"Repository '{validated.repository}' is not in this server's allowed-repository list.",
            )

        if github_client is None:
            return _error_result(validated, "GitHub client is not configured (GITHUB_TOKEN missing).")

        owner, repo = validated.repository.split("/", 1)

        try:
            raw_commits = await github_client.list_commits(
                owner, repo, validated.since, validated.path_filter, validated.max_results
            )
            commits = []
            for raw_commit in raw_commits:
                files = await github_client.get_commit_files(owner, repo, raw_commit["sha"])
                commits.append(shape_commit(raw_commit, files))
        except GitHubNotFoundError:
            return _error_result(
                validated, f"Repository '{validated.repository}' was not found (or the token can't see it)."
            )
        except GitHubRateLimitError:
            logger.error("github_rate_limit_exceeded", extra={"event": "github_rate_limit_exceeded"})
            return _error_result(validated, "GitHub API rate limit exceeded. Try again later.")
        except GitHubAuthError:
            logger.error("github_auth_error", extra={"event": "github_auth_error"})
            return _error_result(validated, "GitHub API authentication failed.")
        except GitHubAPIError:
            logger.exception("github_api_error", extra={"event": "github_api_error"})
            return _error_result(validated, "GitHub API request failed.")

        return {
            "repository": validated.repository,
            "since": validated.since,
            "path_filter": validated.path_filter,
            "commits": commits,
        }


mcp_asgi_app = mcp_server.streamable_http_app()


async def health(request: Request) -> JSONResponse:
    return JSONResponse(
        {"status": "ok", "service": settings.service_name, "environment": settings.environment}
    )


async def readiness(request: Request) -> JSONResponse:
    if github_client is None:
        return JSONResponse(
            {"status": "not_ready", "service": settings.service_name, "github_api": "not_configured"},
            status_code=503,
        )
    ok = await github_client.ping()
    if ok:
        return JSONResponse({"status": "ok", "service": settings.service_name, "github_api": "ok"})
    return JSONResponse(
        {"status": "not_ready", "service": settings.service_name, "github_api": "unreachable"},
        status_code=503,
    )


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    global github_client
    async with mcp_asgi_app.router.lifespan_context(mcp_asgi_app):
        logger.info(
            "github_mcp_startup",
            extra={"event": "github_mcp_startup", "allowed_repositories": settings.allowed_repositories},
        )
        if settings.github_token:
            github_client = GitHubClient(
                token=settings.github_token,
                base_url=settings.github_api_base_url,
                timeout_seconds=settings.github_api_timeout_seconds,
            )
        else:
            logger.warning("github_token_not_configured", extra={"event": "github_token_not_configured"})

        yield

        if github_client is not None:
            await github_client.aclose()
        logger.info("github_mcp_shutdown", extra={"event": "github_mcp_shutdown"})


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
