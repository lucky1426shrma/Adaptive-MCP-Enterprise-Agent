"""Schemas for the DB MCP tool surface.

Phase 2: the schema and its validation rules are real and enforced now,
even though the tool implementation behind it is a stub — this is
deliberate, so the MCP client (Phase 4) can already discover a realistic
tool shape, and so query-limit/date-range validation (a security
requirement) exists from the start rather than being retrofitted once
Phase 5 wires up a real database.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

MAX_DATE_RANGE_DAYS = 90


class PaymentFailureStatsInput(BaseModel):
    start_date: str = Field(..., description="ISO date, e.g. 2026-08-13")
    end_date: str = Field(..., description="ISO date, e.g. 2026-08-14")
    service: Optional[str] = Field(
        default=None, max_length=100, description="Optional service name filter."
    )

    @field_validator("start_date", "end_date")
    @classmethod
    def _must_be_valid_iso_date(cls, value: str) -> str:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"'{value}' is not a valid ISO date (YYYY-MM-DD)") from exc
        return value

    @model_validator(mode="after")
    def _end_after_start_and_within_range(self) -> "PaymentFailureStatsInput":
        start = date.fromisoformat(self.start_date)
        end = date.fromisoformat(self.end_date)
        if end < start:
            raise ValueError("end_date must not be before start_date")
        if (end - start).days > MAX_DATE_RANGE_DAYS:
            raise ValueError(f"date range must not exceed {MAX_DATE_RANGE_DAYS} days")
        return self


class PaymentFailureStatsResult(BaseModel):
    start_date: str
    end_date: str
    service: Optional[str]
    total_attempts: int
    failed_attempts: int
    failure_rate_pct: float
