"""Tests for BearerAuthMiddleware.

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

from app.auth import BearerAuthMiddleware

EXPECTED_TOKEN = "test-token-123"


async def _protected_endpoint(request):
    return JSONResponse({"ok": True})


def _build_app() -> Starlette:
    return Starlette(
        routes=[Route("/protected", _protected_endpoint, methods=["GET"])],
        middleware=[Middleware(BearerAuthMiddleware, expected_token=EXPECTED_TOKEN)],
    )


def test_missing_authorization_header_is_rejected() -> None:
    client = TestClient(_build_app())
    response = client.get("/protected")
    assert response.status_code == 401


def test_wrong_token_is_rejected() -> None:
    client = TestClient(_build_app())
    response = client.get("/protected", headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 401


def test_malformed_header_is_rejected() -> None:
    client = TestClient(_build_app())
    response = client.get("/protected", headers={"Authorization": EXPECTED_TOKEN})  # missing "Bearer "
    assert response.status_code == 401


def test_correct_token_is_accepted() -> None:
    client = TestClient(_build_app())
    response = client.get("/protected", headers={"Authorization": f"Bearer {EXPECTED_TOKEN}"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
