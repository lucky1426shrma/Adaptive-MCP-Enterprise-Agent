"""Tests for BackendAPIKeyMiddleware.

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

from app.security.api_key_middleware import BackendAPIKeyMiddleware

EXPECTED_KEY = "test-backend-key"


async def _ok(request):
    return JSONResponse({"ok": True})


async def _health(request):
    return JSONResponse({"status": "ok"})


def _build_app(expected_key) -> Starlette:
    return Starlette(
        routes=[
            Route("/chat", _ok, methods=["POST"]),
            Route("/health", _health, methods=["GET"]),
        ],
        middleware=[Middleware(BackendAPIKeyMiddleware, expected_key=expected_key)],
    )


def test_disabled_when_no_key_configured() -> None:
    client = TestClient(_build_app(expected_key=None))
    assert client.post("/chat").status_code == 200


def test_disabled_when_empty_string_configured() -> None:
    client = TestClient(_build_app(expected_key=""))
    assert client.post("/chat").status_code == 200


def test_rejects_missing_authorization_header_when_enabled() -> None:
    client = TestClient(_build_app(expected_key=EXPECTED_KEY))
    assert client.post("/chat").status_code == 401


def test_rejects_wrong_key() -> None:
    client = TestClient(_build_app(expected_key=EXPECTED_KEY))
    response = client.post("/chat", headers={"Authorization": "Bearer wrong-key"})
    assert response.status_code == 401


def test_accepts_correct_key() -> None:
    client = TestClient(_build_app(expected_key=EXPECTED_KEY))
    response = client.post("/chat", headers={"Authorization": f"Bearer {EXPECTED_KEY}"})
    assert response.status_code == 200


def test_health_endpoint_exempt_even_when_key_configured() -> None:
    client = TestClient(_build_app(expected_key=EXPECTED_KEY))
    assert client.get("/health").status_code == 200
