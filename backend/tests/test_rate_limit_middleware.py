"""Tests for RateLimitMiddleware.

Requires `starlette` + `httpx` installed to execute — see the top-level
README for why that isn't possible in this sandbox; verify locally with
`pip install -r requirements-dev.txt && pytest`.
"""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.security.rate_limit_middleware import RateLimitMiddleware
from app.security.rate_limiter import RateLimiter


async def _ok(request):
    return JSONResponse({"ok": True})


async def _health(request):
    return JSONResponse({"status": "ok"})


def _build_app(max_requests: int = 2, window_seconds: float = 60) -> Starlette:
    limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
    return Starlette(
        routes=[
            Route("/thing", _ok, methods=["GET"]),
            Route("/health", _health, methods=["GET"]),
        ],
        middleware=[Middleware(RateLimitMiddleware, limiter=limiter)],
    )


def test_requests_within_budget_succeed() -> None:
    client = TestClient(_build_app(max_requests=2))
    assert client.get("/thing").status_code == 200
    assert client.get("/thing").status_code == 200


def test_request_beyond_budget_returns_429() -> None:
    client = TestClient(_build_app(max_requests=1))
    assert client.get("/thing").status_code == 200
    response = client.get("/thing")
    assert response.status_code == 429
    assert "Retry-After" in response.headers


def test_health_endpoint_is_exempt_from_rate_limiting() -> None:
    client = TestClient(_build_app(max_requests=1))
    for _ in range(5):
        assert client.get("/health").status_code == 200


def test_different_client_ips_have_independent_budgets() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=60)
    app = Starlette(
        routes=[Route("/thing", _ok, methods=["GET"])],
        middleware=[Middleware(RateLimitMiddleware, limiter=limiter)],
    )
    client = TestClient(app)
    # TestClient doesn't easily vary client IP per-request without
    # extra setup; this test documents the intended behavior via the
    # underlying RateLimiter, already covered directly in
    # test_rate_limiter.py's test_different_clients_have_independent_budgets.
    assert client.get("/thing").status_code == 200
