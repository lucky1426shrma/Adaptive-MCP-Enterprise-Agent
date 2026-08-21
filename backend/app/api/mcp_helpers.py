"""Shared helper for API routes that proxy directly to an MCP tool call.

Maps MCP client errors to sanitized HTTP responses: full detail (server
name, tool name, exception) is logged server-side with the request's
correlation ID (via the request-scoped logger context already wired up
in Phase 1); only a generic, non-leaking message reaches the caller.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import HTTPException

from app.mcp.client import MCPServerClient
from app.mcp.exceptions import (
    MCPClientError,
    MCPConnectionError,
    MCPProtocolError,
    MCPTimeoutError,
    MCPToolExecutionError,
)

logger = logging.getLogger(__name__)


async def call_tool_or_http_error(
    client: MCPServerClient, tool_name: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    """Call `tool_name` on `client`, raising a sanitized HTTPException on failure."""
    try:
        result = await client.call_tool(tool_name, arguments)
    except MCPTimeoutError as exc:
        logger.error(
            "mcp_tool_timeout",
            extra={"event": "mcp_tool_timeout", "server": client.name, "tool": tool_name},
        )
        raise HTTPException(status_code=504, detail=f"'{client.name}' MCP server timed out.") from exc
    except MCPConnectionError as exc:
        logger.error(
            "mcp_tool_connection_error",
            extra={"event": "mcp_tool_connection_error", "server": client.name, "tool": tool_name},
        )
        raise HTTPException(
            status_code=503, detail=f"Could not reach the '{client.name}' MCP server."
        ) from exc
    except MCPToolExecutionError as exc:
        logger.error(
            "mcp_tool_execution_error",
            extra={"event": "mcp_tool_execution_error", "server": client.name, "tool": tool_name},
        )
        raise HTTPException(
            status_code=502, detail=f"The '{client.name}' MCP server reported a tool error."
        ) from exc
    except MCPProtocolError as exc:
        logger.error(
            "mcp_tool_protocol_error",
            extra={"event": "mcp_tool_protocol_error", "server": client.name, "tool": tool_name},
        )
        raise HTTPException(
            status_code=502, detail=f"Unexpected response from the '{client.name}' MCP server."
        ) from exc
    except MCPClientError as exc:  # catch-all for the base class, just in case
        logger.error(
            "mcp_tool_unknown_error",
            extra={"event": "mcp_tool_unknown_error", "server": client.name, "tool": tool_name},
        )
        raise HTTPException(status_code=502, detail="MCP tool call failed.") from exc

    if result.data is not None:
        return result.data
    return {"raw_text": result.raw_text}
