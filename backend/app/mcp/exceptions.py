"""Exception hierarchy for the backend's MCP client layer.

Each MCP failure mode gets a distinct type so callers (API routes, and
later the LangGraph agent) can react differently — e.g. a timeout might
be worth a retry with a different tool, a tool-execution error should
be reported as evidence-gathering failure, a connection error means the
server is down entirely. All are caught, logged with full detail
server-side, and mapped to a SANITIZED message before reaching the
end user (see app/api/mcp_helpers.py) — never leak MCP server URLs,
tokens, or stack traces to the client.
"""

from __future__ import annotations


class MCPClientError(Exception):
    """Base class for all MCP client errors."""


class MCPConnectionError(MCPClientError):
    """Could not establish a connection/session with the MCP server."""


class MCPTimeoutError(MCPClientError):
    """The MCP server did not respond within the configured timeout."""


class MCPToolExecutionError(MCPClientError):
    """The MCP server executed the tool but reported an error result
    (i.e. the MCP protocol round-trip succeeded, but `isError` was set)."""


class MCPProtocolError(MCPClientError):
    """The MCP server returned a response that didn't match the expected
    protocol shape (e.g. no content blocks, unexpected structure)."""
