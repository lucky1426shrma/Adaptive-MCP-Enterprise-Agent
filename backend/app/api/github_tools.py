"""GitHub MCP integration endpoint.

Same caveat as app/api/rag_tools.py and app/api/db_tools.py: a
Phase 6 integration-proof endpoint, not the final chat API.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.api.mcp_helpers import call_tool_or_http_error
from app.mcp.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/github", tags=["mcp-github"])


class SearchRecentCommitsRequest(BaseModel):
    repository: str = Field(..., min_length=1, max_length=200)
    since: str = Field(..., description="ISO date, e.g. 2026-08-01")
    path_filter: Optional[str] = Field(default=None, max_length=300)
    max_results: int = Field(default=10, ge=1, le=20)

    @field_validator("since")
    @classmethod
    def _valid_iso_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid ISO date (YYYY-MM-DD)") from exc
        return value

    @field_validator("repository")
    @classmethod
    def _owner_repo_format(cls, value: str) -> str:
        if "/" not in value or value.startswith("/") or value.endswith("/"):
            raise ValueError("repository must be in 'owner/name' format")
        return value


def _require_github_client():
    client = registry.get("github")
    if client is None:
        raise HTTPException(status_code=503, detail="GitHub MCP is not configured.")
    return client


@router.post("/search-commits", summary="Call the GitHub MCP search_recent_commits tool")
async def search_recent_commits(payload: SearchRecentCommitsRequest) -> Dict[str, Any]:
    client = _require_github_client()
    return await call_tool_or_http_error(
        client,
        "search_recent_commits",
        {
            "repository": payload.repository,
            "since": payload.since,
            "path_filter": payload.path_filter,
            "max_results": payload.max_results,
        },
    )
