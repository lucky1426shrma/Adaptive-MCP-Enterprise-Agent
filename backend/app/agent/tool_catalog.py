"""Discovers and caches the flattened, agent-facing tool catalog across
all registered MCP servers.

Tool names are prefixed with their server (`rag__search_knowledge`) so
the LLM sees one flat, unambiguous tool list even though the tools live
behind three separate MCP servers/trust boundaries. This module is also
what maps a tool call the LLM makes back to which MCP server must
execute it — `resolve()` is the routing table `app/agent/nodes.py`
uses.

`MCPRegistry` is imported only under `TYPE_CHECKING` (not at runtime),
so this module has ZERO hard dependency on `mcp`/`httpx` — see
`backend/tests/test_tool_catalog.py`, which exercises `refresh()` and
`resolve()` against fake registries/clients and actually runs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict, List, Tuple

from app.llm.schemas import ToolDefinition

if TYPE_CHECKING:
    from app.mcp.registry import MCPRegistry

logger = logging.getLogger(__name__)

_SEPARATOR = "__"


class ToolCatalog:
    def __init__(self) -> None:
        self._tools: List[ToolDefinition] = []
        self._routes: Dict[str, Tuple[str, str]] = {}  # prefixed_name -> (server, original_name)
        self._loaded_servers: List[str] = []

    @property
    def tools(self) -> List[ToolDefinition]:
        return list(self._tools)

    @property
    def is_empty(self) -> bool:
        return len(self._tools) == 0

    @property
    def loaded_servers(self) -> List[str]:
        return list(self._loaded_servers)

    def has_tool(self, prefixed_name: str) -> bool:
        return prefixed_name in self._routes

    def resolve(self, prefixed_name: str) -> Tuple[str, str]:
        if prefixed_name not in self._routes:
            raise KeyError(f"Unknown tool '{prefixed_name}'")
        return self._routes[prefixed_name]

    async def refresh(self, registry: "MCPRegistry") -> None:
        """Rebuild the catalog by discovering tools from every registered
        MCP server. A server that fails to respond is skipped (logged),
        not fatal — the agent runs with whatever tools ARE reachable,
        consistent with the project's "run with a subset of MCP servers
        available" philosophy from earlier phases.
        """
        tools: List[ToolDefinition] = []
        routes: Dict[str, Tuple[str, str]] = {}
        loaded_servers: List[str] = []

        for server_name, client in registry.all().items():
            try:
                server_tools = await client.list_tools()
            except Exception:  # noqa: BLE001 - one unreachable server must not block the others
                logger.warning(
                    "tool_catalog_server_unreachable",
                    extra={"event": "tool_catalog_server_unreachable", "server": server_name},
                )
                continue

            for tool in server_tools:
                prefixed_name = f"{server_name}{_SEPARATOR}{tool.name}"
                tools.append(
                    ToolDefinition(
                        name=prefixed_name,
                        description=tool.description or "",
                        parameters=tool.input_schema or {"type": "object", "properties": {}},
                    )
                )
                routes[prefixed_name] = (server_name, tool.name)
            loaded_servers.append(server_name)

        self._tools = tools
        self._routes = routes
        self._loaded_servers = loaded_servers
        logger.info(
            "tool_catalog_refreshed",
            extra={"event": "tool_catalog_refreshed", "tool_count": len(tools), "servers": loaded_servers},
        )


# Process-wide singleton, refreshed by AgentService on first use (or
# whenever explicitly refreshed) — see app/agent/service.py.
catalog = ToolCatalog()
