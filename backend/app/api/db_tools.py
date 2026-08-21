"""DB MCP integration endpoint.

Same caveat as app/api/rag_tools.py: a Phase 5 integration-proof
endpoint, not the final chat API.

NOTE on validation duplication: the date-range rules below (valid ISO
dates, end >= start, max 90-day range) intentionally mirror db-mcp's
own `PaymentFailureStatsInput` validation. This is defense in depth,
not accidental duplication — the backend validates early for a fast,
clear error before even attempting the MCP call, while db-mcp validates
independently because it must never trust its caller, even though today
the only caller is this backend (each MCP server is its own trust
boundary; see the security spec).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from app.api.mcp_helpers import call_tool_or_http_error
from app.mcp.registry import registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp/db", tags=["mcp-db"])

MAX_DATE_RANGE_DAYS = 90


class PaymentFailureStatsRequest(BaseModel):
    start_date: str = Field(..., description="ISO date, e.g. 2026-08-13")
    end_date: str = Field(..., description="ISO date, e.g. 2026-08-14")
    service: Optional[str] = Field(default=None, max_length=100)

    @field_validator("start_date", "end_date")
    @classmethod
    def _valid_iso_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid ISO date (YYYY-MM-DD)") from exc
        return value

    @model_validator(mode="after")
    def _range_is_sane(self) -> "PaymentFailureStatsRequest":
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)
        if end < start:
            raise ValueError("end_date must not be before start_date")
        if (end - start).days > MAX_DATE_RANGE_DAYS:
            raise ValueError(f"date range must not exceed {MAX_DATE_RANGE_DAYS} days")
        return self


def _require_db_client():
    client = registry.get("db")
    if client is None:
        raise HTTPException(status_code=503, detail="DB MCP is not configured.")
    return client


@router.post("/payment-failure-stats", summary="Call the DB MCP get_payment_failure_stats tool")
async def payment_failure_stats(payload: PaymentFailureStatsRequest) -> Dict[str, Any]:
    client = _require_db_client()
    return await call_tool_or_http_error(
        client,
        "get_payment_failure_stats",
        {"start_date": payload.start_date, "end_date": payload.end_date, "service": payload.service},
    )
