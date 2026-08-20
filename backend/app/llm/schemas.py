"""Internal agent data structures.

Deliberately plain `dataclasses`, not `pydantic.BaseModel`: these are
internal representations used by the agent graph and LLM provider
layer, never directly serialized as FastAPI request/response bodies
(those live in `app/api/chat.py` as their own pydantic models). Using
dataclasses here keeps this module dependency-free — no `pydantic`
import — which is what makes `app/agent/nodes.py`,
`app/agent/tool_catalog.py`, and `app/llm/openrouter_format.py`
testable without installing the full dependency stack (see their
respective test files, which actually run).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ChatRole(str, Enum):
    system = "system"
    user = "user"
    assistant = "assistant"
    tool = "tool"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatMessage:
    role: ChatRole
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    # Only set on role=tool messages: which call this is a result for,
    # and (redundantly, for readability in logs/traces) which tool name.
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


@dataclass
class ToolDefinition:
    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})


@dataclass
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMResponse:
    message: ChatMessage
    usage: LLMUsage = field(default_factory=LLMUsage)
    model: str = ""
    finish_reason: Optional[str] = None
    latency_ms: float = 0.0
