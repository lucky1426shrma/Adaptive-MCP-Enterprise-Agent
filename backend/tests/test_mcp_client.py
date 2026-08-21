"""Tests for MCPServerClient's error handling and result parsing.

Requires `mcp` (and its transitive deps) installed to execute — this
module imports `app.mcp.client`, which itself imports the `mcp` SDK.
See the top-level README for why that isn't possible in this sandbox;
verify locally with `pip install -r requirements-dev.txt && pytest`.

Strategy: monkeypatch `MCPServerClient._session` to yield a fake session
object, so these tests exercise the timeout/error-mapping/parsing logic
in `client.py` without a real MCP server or real transport.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from app.mcp.client import MCPServerClient
from app.mcp.exceptions import MCPProtocolError, MCPToolExecutionError, MCPTimeoutError


class _FakeSession:
    def __init__(self, tool_result=None, tools_result=None, raise_on_call: Exception | None = None) -> None:
        self._tool_result = tool_result
        self._tools_result = tools_result
        self._raise_on_call = raise_on_call

    async def call_tool(self, name: str, arguments: dict):
        if self._raise_on_call:
            raise self._raise_on_call
        return self._tool_result

    async def list_tools(self):
        return self._tools_result


def _client_with_fake_session(fake_session: _FakeSession, timeout_seconds: float = 5.0) -> MCPServerClient:
    client = MCPServerClient(name="test", url="http://example.invalid/mcp", auth_token="tok", timeout_seconds=timeout_seconds)

    @asynccontextmanager
    async def _fake_session_ctx():
        yield fake_session

    client._session = _fake_session_ctx  # type: ignore[method-assign]
    return client


def _text_result(text: str, is_error: bool = False):
    return SimpleNamespace(content=[SimpleNamespace(text=text)], isError=is_error)


@pytest.mark.asyncio
async def test_call_tool_parses_successful_json_result() -> None:
    fake = _FakeSession(tool_result=_text_result('{"results": ["a", "b"]}', is_error=False))
    client = _client_with_fake_session(fake)

    result = await client.call_tool("search_knowledge", {"query": "x"})

    assert result.data == {"results": ["a", "b"]}
    assert result.server == "test"
    assert result.tool_name == "search_knowledge"


@pytest.mark.asyncio
async def test_call_tool_raises_execution_error_when_is_error_true() -> None:
    fake = _FakeSession(tool_result=_text_result('{"error": "boom"}', is_error=True))
    client = _client_with_fake_session(fake)

    with pytest.raises(MCPToolExecutionError):
        await client.call_tool("search_knowledge", {"query": "x"})


@pytest.mark.asyncio
async def test_list_tools_maps_result_to_tool_info() -> None:
    fake_tool = SimpleNamespace(name="search_knowledge", description="desc", inputSchema={"type": "object"})
    fake = _FakeSession(tools_result=SimpleNamespace(tools=[fake_tool]))
    client = _client_with_fake_session(fake)

    tools = await client.list_tools()

    assert len(tools) == 1
    assert tools[0].name == "search_knowledge"
    assert tools[0].description == "desc"


@pytest.mark.asyncio
async def test_unexpected_exception_during_call_becomes_protocol_error() -> None:
    fake = _FakeSession(raise_on_call=RuntimeError("something broke"))
    client = _client_with_fake_session(fake)

    with pytest.raises(MCPProtocolError):
        await client.call_tool("search_knowledge", {"query": "x"})
