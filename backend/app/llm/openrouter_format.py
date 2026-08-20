"""Pure request/response shaping between this project's internal
ChatMessage/ToolDefinition/LLMResponse types and OpenRouter's
OpenAI-compatible chat completions wire format.

Split out from `openrouter_provider.py` specifically so this can be
unit tested without `httpx` installed — the actual HTTP call is the
only part of that module needing it. See `backend/tests/test_openrouter_format.py`,
which actually runs.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from app.llm.exceptions import LLMResponseError
from app.llm.schemas import ChatMessage, ChatRole, ToolCall, ToolDefinition


def message_to_openrouter(message: ChatMessage) -> Dict[str, Any]:
    if message.role == ChatRole.tool:
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id or "call_0",
            "name": message.name,
            "content": message.content or "",
        }

    payload: Dict[str, Any] = {"role": message.role.value, "content": message.content}

    if message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": tc.id or f"call_{i}",
                "type": "function",
                "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
            }
            for i, tc in enumerate(message.tool_calls)
        ]

    return payload


def tool_to_openrouter(tool: ToolDefinition) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def parse_tool_calls(raw_tool_calls: Optional[List[Dict[str, Any]]]) -> Optional[List[ToolCall]]:
    """Parse OpenRouter/OpenAI-shaped `tool_calls` into our `ToolCall` list.

    Raises `LLMResponseError` (never a bare exception) if the model
    returned tool-call arguments that aren't valid JSON, or that parse
    to something other than a JSON object — both are cases where we'd
    otherwise silently hand a bad tool call downstream.
    """
    if not raw_tool_calls:
        return None

    parsed: List[ToolCall] = []
    for idx, raw in enumerate(raw_tool_calls):
        function = raw.get("function", {}) or {}
        raw_arguments = function.get("arguments")

        if raw_arguments is None:
            arguments: Any = {}
        elif isinstance(raw_arguments, dict):
            arguments = raw_arguments
        elif isinstance(raw_arguments, str):
            trimmed = raw_arguments.strip()
            if not trimmed:
                arguments = {}
            else:
                # Strip markdown code blocks if the model wrapped JSON in ```json ... ```
                if trimmed.startswith("```"):
                    lines = trimmed.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].strip() == "```":
                        lines = lines[:-1]
                    trimmed = "\n".join(lines).strip()
                try:
                    arguments = json.loads(trimmed)
                except json.JSONDecodeError as exc:
                    raise LLMResponseError(
                        f"Model returned malformed tool call arguments for "
                        f"'{function.get('name')}': {raw_arguments!r}"
                    ) from exc
        else:
            raise LLMResponseError(
                f"Model returned unexpected tool call arguments type for "
                f"'{function.get('name')}': {type(raw_arguments).__name__}"
            )

        if not isinstance(arguments, dict):
            raise LLMResponseError(
                f"Model returned non-object tool call arguments for "
                f"'{function.get('name')}': {raw_arguments!r}"
            )

        call_id = raw.get("id") or f"call_{idx}_{int(time.time() * 1000)}"
        parsed.append(ToolCall(id=call_id, name=function.get("name", ""), arguments=arguments))

    return parsed
