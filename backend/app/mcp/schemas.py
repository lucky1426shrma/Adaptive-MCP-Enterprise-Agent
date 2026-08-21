"""Schemas for the backend's MCP client layer (tool discovery / call results)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MCPToolInfo(BaseModel):
    name: str
    description: Optional[str] = None
    input_schema: Dict[str, Any] = Field(default_factory=dict)


class MCPToolCallResult(BaseModel):
    server: str
    tool_name: str
    data: Optional[Dict[str, Any]] = None
    raw_text: Optional[str] = None
    latency_ms: float
