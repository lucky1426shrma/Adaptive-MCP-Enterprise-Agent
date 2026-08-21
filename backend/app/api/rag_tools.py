"""RAG MCP integration endpoints.

IMPORTANT: these are Phase 4 integration-proof endpoints — they exist to
verify the MCP client layer (discovery, invocation, parsing, error
handling) works end-to-end over real HTTP, before the LangGraph agent
exists. They are NOT the final chat API. Once the agent lands (Phase 7),
tool selection and invocation move into the agent graph; these routes
either get removed or repurposed as manual debugging endpoints.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.mcp_helpers import call_tool_or_http_error
from app.mcp.exceptions import MCPClientError, MCPConnectionError, MCPTimeoutError
from app.mcp.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/rag", tags=["mcp-rag"])


class SearchKnowledgeRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


def _require_rag_client():
    client = registry.get("rag")
    if client is None:
        raise HTTPException(status_code=503, detail="RAG MCP is not configured.")
    return client


@router.get("/tools", summary="Discover tools exposed by the RAG MCP server")
async def list_rag_tools() -> List[Dict[str, Any]]:
    client = _require_rag_client()
    try:
        tools = await client.list_tools()
    except MCPTimeoutError as exc:
        raise HTTPException(status_code=504, detail="RAG MCP server timed out.") from exc
    except MCPConnectionError as exc:
        raise HTTPException(status_code=503, detail="Could not reach the RAG MCP server.") from exc
    except MCPClientError as exc:
        logger.error("rag_mcp_list_tools_failed", extra={"event": "rag_mcp_list_tools_failed"})
        raise HTTPException(status_code=502, detail="Failed to discover RAG MCP tools.") from exc

    return [t.model_dump() for t in tools]


@router.post("/search", summary="Call the RAG MCP search_knowledge tool")
async def search_knowledge(payload: SearchKnowledgeRequest) -> Dict[str, Any]:
    client = _require_rag_client()
    return await call_tool_or_http_error(
        client, "search_knowledge", {"query": payload.query, "top_k": payload.top_k}
    )
