"""Schemas for the GitHub MCP tool surface."""

from __future__ import annotations

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SearchRecentCommitsInput(BaseModel):
    repository: str = Field(
        ..., min_length=1, max_length=200, description="e.g. 'org/payment-service'"
    )
    since: str = Field(..., description="ISO date; only commits on/after this date.")
    path_filter: Optional[str] = Field(
        default=None, max_length=300, description="Optional path prefix filter, e.g. 'src/payments/'."
    )
    max_results: int = Field(
        default=10, ge=1, le=20, description="Maximum commits to return (1-20)."
    )

    @field_validator("since")
    @classmethod
    def _must_be_valid_iso_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid ISO date (YYYY-MM-DD)") from exc
        return value

    @field_validator("repository")
    @classmethod
    def _must_look_like_owner_repo(cls, value: str) -> str:
        if "/" not in value or value.startswith("/") or value.endswith("/"):
            raise ValueError("repository must be in 'owner/name' format")
        return value


class CommitSummary(BaseModel):
    sha: str
    message: str
    author: str
    date: str
    files_changed: List[str]


class SearchRecentCommitsResult(BaseModel):
    repository: str
    since: str
    path_filter: Optional[str]
    commits: List[CommitSummary]
