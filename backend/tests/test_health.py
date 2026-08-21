"""Tests for Phase 1: health endpoints and request-context middleware."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"]
    assert body["version"]
    assert body["environment"]


def test_readiness_returns_ok() -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_response_includes_request_id_header() -> None:
    response = client.get("/health")
    headers_lower = {k.lower() for k in response.headers.keys()}
    assert "x-request-id" in headers_lower
    # A UUID4 was generated since no request ID was supplied.
    assert len(response.headers["x-request-id"]) > 0


def test_custom_request_id_is_echoed_back() -> None:
    custom_id = "test-request-id-123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.headers["x-request-id"] == custom_id


def test_unknown_route_returns_404() -> None:
    """Failure path: hitting a nonexistent route should 404 cleanly,
    not raise an unhandled exception."""
    response = client.get("/does-not-exist")
    assert response.status_code == 404


def test_wrong_method_returns_405() -> None:
    """Failure path: unsupported method on a known route."""
    response = client.post("/health")
    assert response.status_code == 405
