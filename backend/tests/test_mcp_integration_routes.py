"""Tests for the /mcp/rag and /mcp/db integration endpoints.

Requires `fastapi`, `httpx`, `mcp` installed to execute — see the
top-level README. Strategy: register a fake MCPServerClient directly
into `app.mcp.registry.registry` before making requests, rather than
standing up a real MCP server.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.mcp.exceptions import MCPConnectionError, MCPTimeoutError, MCPToolExecutionError
from app.mcp.registry import registry
from app.mcp.schemas import MCPToolCallResult, MCPToolInfo

client = TestClient(app)


class _FakeMCPClient:
    def __init__(self, name: str) -> None:
        self.name = name
        self._call_result: MCPToolCallResult | None = None
        self._call_exception: Exception | None = None
        self._tools: list[MCPToolInfo] = []

    def set_call_result(self, data: Dict[str, Any]) -> None:
        self._call_result = MCPToolCallResult(server=self.name, tool_name="stub", data=data, latency_ms=1.0)
        self._call_exception = None

    def set_call_exception(self, exc: Exception) -> None:
        self._call_exception = exc

    def set_tools(self, tools: list[MCPToolInfo]) -> None:
        self._tools = tools

    async def call_tool(self, tool_name: str, arguments: dict) -> MCPToolCallResult:
        if self._call_exception:
            raise self._call_exception
        assert self._call_result is not None
        return self._call_result

    async def list_tools(self) -> list[MCPToolInfo]:
        return self._tools


@pytest.fixture(autouse=True)
def _reset_registry():
    yield
    registry._clients.clear()  # noqa: SLF001 - test cleanup only


def test_search_endpoint_returns_503_when_rag_not_configured() -> None:
    registry._clients.clear()  # noqa: SLF001
    response = client.post("/mcp/rag/search", json={"query": "March incident", "top_k": 3})
    assert response.status_code == 503


def test_search_endpoint_returns_data_on_success() -> None:
    fake = _FakeMCPClient("rag")
    fake.set_call_result({"query": "March incident", "results": []})
    registry.register("rag", fake)  # type: ignore[arg-type]

    response = client.post("/mcp/rag/search", json={"query": "March incident", "top_k": 3})

    assert response.status_code == 200
    assert response.json()["query"] == "March incident"


def test_search_endpoint_maps_timeout_to_504() -> None:
    fake = _FakeMCPClient("rag")
    fake.set_call_exception(MCPTimeoutError("timed out"))
    registry.register("rag", fake)  # type: ignore[arg-type]

    response = client.post("/mcp/rag/search", json={"query": "x", "top_k": 3})
    assert response.status_code == 504


def test_search_endpoint_maps_connection_error_to_503() -> None:
    fake = _FakeMCPClient("rag")
    fake.set_call_exception(MCPConnectionError("down"))
    registry.register("rag", fake)  # type: ignore[arg-type]

    response = client.post("/mcp/rag/search", json={"query": "x", "top_k": 3})
    assert response.status_code == 503


def test_search_endpoint_maps_tool_execution_error_to_502() -> None:
    fake = _FakeMCPClient("rag")
    fake.set_call_exception(MCPToolExecutionError("bad tool call"))
    registry.register("rag", fake)  # type: ignore[arg-type]

    response = client.post("/mcp/rag/search", json={"query": "x", "top_k": 3})
    assert response.status_code == 502


def test_search_endpoint_rejects_invalid_top_k() -> None:
    fake = _FakeMCPClient("rag")
    fake.set_call_result({"query": "x", "results": []})
    registry.register("rag", fake)  # type: ignore[arg-type]

    response = client.post("/mcp/rag/search", json={"query": "x", "top_k": 999})
    assert response.status_code == 422


def test_list_rag_tools_returns_tool_list() -> None:
    fake = _FakeMCPClient("rag")
    fake.set_tools([MCPToolInfo(name="search_knowledge", description="desc")])
    registry.register("rag", fake)  # type: ignore[arg-type]

    response = client.get("/mcp/rag/tools")
    assert response.status_code == 200
    assert response.json()[0]["name"] == "search_knowledge"


def test_payment_failure_stats_endpoint_returns_503_when_db_not_configured() -> None:
    registry._clients.clear()  # noqa: SLF001
    response = client.post(
        "/mcp/db/payment-failure-stats", json={"start_date": "2026-08-01", "end_date": "2026-08-02"}
    )
    assert response.status_code == 503


def test_payment_failure_stats_endpoint_rejects_invalid_range() -> None:
    fake = _FakeMCPClient("db")
    fake.set_call_result({"total_attempts": 100, "failed_attempts": 2})
    registry.register("db", fake)  # type: ignore[arg-type]

    response = client.post(
        "/mcp/db/payment-failure-stats", json={"start_date": "2026-08-14", "end_date": "2026-08-01"}
    )
    assert response.status_code == 422


def test_payment_failure_stats_endpoint_rejects_range_over_90_days() -> None:
    fake = _FakeMCPClient("db")
    fake.set_call_result({"total_attempts": 100, "failed_attempts": 2})
    registry.register("db", fake)  # type: ignore[arg-type]

    response = client.post(
        "/mcp/db/payment-failure-stats", json={"start_date": "2026-01-01", "end_date": "2026-08-01"}
    )
    assert response.status_code == 422


def test_payment_failure_stats_endpoint_returns_data_on_success() -> None:
    fake = _FakeMCPClient("db")
    fake.set_call_result({"total_attempts": 5000, "failed_attempts": 105, "failure_rate_pct": 2.1})
    registry.register("db", fake)  # type: ignore[arg-type]

    response = client.post(
        "/mcp/db/payment-failure-stats", json={"start_date": "2026-08-14", "end_date": "2026-08-14"}
    )
    assert response.status_code == 200
    assert response.json()["failure_rate_pct"] == 2.1


def test_search_commits_endpoint_returns_503_when_github_not_configured() -> None:
    registry._clients.clear()  # noqa: SLF001
    response = client.post(
        "/mcp/github/search-commits", json={"repository": "myorg/payment-service", "since": "2026-08-01"}
    )
    assert response.status_code == 503


def test_search_commits_endpoint_rejects_malformed_repository() -> None:
    fake = _FakeMCPClient("github")
    fake.set_call_result({"repository": "x", "commits": []})
    registry.register("github", fake)  # type: ignore[arg-type]

    response = client.post(
        "/mcp/github/search-commits", json={"repository": "no-slash", "since": "2026-08-01"}
    )
    assert response.status_code == 422


def test_search_commits_endpoint_rejects_invalid_date() -> None:
    fake = _FakeMCPClient("github")
    fake.set_call_result({"repository": "x", "commits": []})
    registry.register("github", fake)  # type: ignore[arg-type]

    response = client.post(
        "/mcp/github/search-commits",
        json={"repository": "myorg/payment-service", "since": "not-a-date"},
    )
    assert response.status_code == 422


def test_search_commits_endpoint_returns_data_on_success() -> None:
    fake = _FakeMCPClient("github")
    fake.set_call_result(
        {
            "repository": "myorg/payment-service",
            "since": "2026-03-14",
            "commits": [{"sha": "abc123", "message": "Fix pool size", "author": "a", "date": "d", "files_changed": []}],
        }
    )
    registry.register("github", fake)  # type: ignore[arg-type]

    response = client.post(
        "/mcp/github/search-commits", json={"repository": "myorg/payment-service", "since": "2026-03-14"}
    )
    assert response.status_code == 200
    assert response.json()["commits"][0]["sha"] == "abc123"


def test_search_commits_endpoint_maps_timeout_to_504() -> None:
    fake = _FakeMCPClient("github")
    fake.set_call_exception(MCPTimeoutError("timed out"))
    registry.register("github", fake)  # type: ignore[arg-type]

    response = client.post(
        "/mcp/github/search-commits", json={"repository": "myorg/payment-service", "since": "2026-08-01"}
    )
    assert response.status_code == 504
