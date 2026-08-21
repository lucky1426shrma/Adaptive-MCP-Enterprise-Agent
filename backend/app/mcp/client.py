"""MCP client: the backend's connection to a single remote MCP server.

This is the ONLY place in the backend that speaks the MCP protocol.
API routes and (later) the LangGraph agent call `list_tools()` /
`call_tool()` on an `MCPServerClient` instance; they never construct
MCP sessions themselves.

CONNECTION STRATEGY: a fresh Streamable HTTP session (connect ->
initialize -> operate -> close) is opened for EVERY call, rather than
holding one long-lived session across requests. This is simpler and
more robust — no shared mutable session state to corrupt under
concurrent requests, no stale-session reconnect logic needed — at the
cost of paying the MCP initialize handshake on every call. For a
portfolio project this trade-off favors correctness and simplicity;
connection/session pooling is a documented known optimization, not
implemented here (see README "Known limitations").

VERSION CAVEAT: like `services/rag-mcp/app/server.py`, this was written
against my understanding of the `mcp` Python SDK's client API
(`mcp.ClientSession`, `mcp.client.streamable_http.streamablehttp_client`)
without the ability to install/run it in the environment this was
built in. Verify against your installed SDK version — see
`backend/tests/test_mcp_client.py` and the manual verification steps in
the root README.
"""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.mcp.exceptions import (
    MCPConnectionError,
    MCPProtocolError,
    MCPTimeoutError,
    MCPToolExecutionError,
)
from app.mcp.parsing import parse_tool_result_content
from app.mcp.schemas import MCPToolCallResult, MCPToolInfo
from app.observability.span_helper import start_span

logger = logging.getLogger(__name__)


class MCPServerClient:
    """Client for one remote MCP server, reached over Streamable HTTP."""

    def __init__(self, name: str, url: str, auth_token: str, timeout_seconds: float = 30.0) -> None:
        self.name = name
        self.url = url
        self.timeout_seconds = timeout_seconds
        self._auth_token = auth_token

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self._auth_token}"}

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        try:
            async with streamablehttp_client(self.url, headers=self._headers()) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    yield session
        except (MCPConnectionError, MCPTimeoutError):
            raise
        except Exception as exc:  # noqa: BLE001 - deliberately broad: any transport/protocol failure becomes a typed error
            raise MCPConnectionError(
                f"Failed to connect to MCP server '{self.name}' at {self.url}"
            ) from exc

    async def list_tools(self) -> List[MCPToolInfo]:
        with start_span("mcp.list_tools", {"mcp.server": self.name}):
            logger.info("mcp_list_tools_started", extra={"event": "mcp_list_tools_started", "server": self.name})
            try:
                async with asyncio.timeout(self.timeout_seconds):
                    async with self._session() as session:
                        result = await session.list_tools()
            except TimeoutError as exc:
                logger.error(
                    "mcp_list_tools_timeout",
                    extra={"event": "mcp_list_tools_timeout", "server": self.name},
                )
                raise MCPTimeoutError(
                    f"Listing tools on MCP server '{self.name}' timed out after {self.timeout_seconds}s"
                ) from exc
            except MCPConnectionError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise MCPProtocolError(
                    f"Unexpected error listing tools on MCP server '{self.name}'"
                ) from exc

            tools = [
                MCPToolInfo(name=t.name, description=getattr(t, "description", None), input_schema=getattr(t, "inputSchema", {}) or {})
                for t in result.tools
            ]
            logger.info(
                "mcp_list_tools_succeeded",
                extra={"event": "mcp_list_tools_succeeded", "server": self.name, "tool_count": len(tools)},
            )
            return tools

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPToolCallResult:
        with start_span("mcp.call_tool", {"mcp.server": self.name, "mcp.tool": tool_name}):
            logger.info(
                "mcp_tool_call_started",
                extra={"event": "mcp_tool_call_started", "server": self.name, "tool": tool_name},
            )
            start = time.perf_counter()

            try:
                async with asyncio.timeout(self.timeout_seconds):
                    async with self._session() as session:
                        result = await session.call_tool(tool_name, arguments)
            except TimeoutError as exc:
                logger.error(
                    "mcp_tool_call_timeout",
                    extra={"event": "mcp_tool_call_timeout", "server": self.name, "tool": tool_name},
                )
                raise MCPTimeoutError(
                    f"Tool call '{tool_name}' on MCP server '{self.name}' timed out after {self.timeout_seconds}s"
                ) from exc
            except MCPConnectionError:
                raise
            except Exception as exc:  # noqa: BLE001
                raise MCPProtocolError(
                    f"Unexpected error calling tool '{tool_name}' on MCP server '{self.name}'"
                ) from exc

            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            data, raw_text = parse_tool_result_content(result)
            is_error = bool(getattr(result, "isError", False))

            if is_error:
                logger.warning(
                    "mcp_tool_call_reported_error",
                    extra={
                        "event": "mcp_tool_call_reported_error",
                        "server": self.name,
                        "tool": tool_name,
                        "latency_ms": latency_ms,
                    },
                )
                raise MCPToolExecutionError(
                    f"Tool '{tool_name}' on MCP server '{self.name}' reported an error: "
                    f"{raw_text or data or 'no error detail returned'}"
                )

            logger.info(
                "mcp_tool_call_succeeded",
                extra={
                    "event": "mcp_tool_call_succeeded",
                    "server": self.name,
                    "tool": tool_name,
                    "latency_ms": latency_ms,
                },
            )
            return MCPToolCallResult(
                server=self.name, tool_name=tool_name, data=data, raw_text=raw_text, latency_ms=latency_ms
            )
