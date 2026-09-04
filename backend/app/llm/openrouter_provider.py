"""OpenRouterProvider: the only concrete LLMProvider implementation.

Talks to OpenRouter's OpenAI-compatible `/chat/completions` endpoint.
LangGraph and the rest of the agent only ever see the `LLMProvider`
abstraction (`app/llm/provider.py`) — this is the one module that knows
OpenRouter-specific request/response shapes, so the provider can be
swapped later without touching the agent graph, MCP client, or FastAPI
layer, per the project's provider-abstraction requirement.

VERSION CAVEAT: OpenRouter's chat completions endpoint is documented as
OpenAI-API-compatible, including function/tool calling and a `usage`
block in non-streamed responses — this is OpenRouter's core, stable
value proposition, and considerably more stable ground than, say, the
MCP SDK's internal mounting details flagged elsewhere in this project.
Still worth a quick manual check against current OpenRouter docs if a
response doesn't match the shape assumed here.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from app.llm.exceptions import (
    LLMAuthError,
    LLMConnectionError,
    LLMModelUnavailableError,
    LLMRateLimitError,
    LLMResponseError,
    LLMTimeoutError,
)
from app.llm.openrouter_format import message_to_openrouter, parse_tool_calls, tool_to_openrouter
from app.llm.provider import LLMProvider
from app.llm.schemas import ChatMessage, ChatRole, LLMResponse, LLMUsage, ToolDefinition
from app.observability.span_helper import start_span

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 60.0,
    ) -> None:
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured.")
        if not model:
            raise RuntimeError("OPENROUTER_MODEL is not configured.")

        self._model = model
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def chat(
        self, messages: List[ChatMessage], tools: Optional[List[ToolDefinition]] = None
    ) -> LLMResponse:
        with start_span(
            "llm.chat", {"llm.model": self._model, "llm.tools_offered": len(tools) if tools else 0}
        ):
            body: Dict[str, Any] = {
                "model": self._model,
                "messages": [message_to_openrouter(m) for m in messages],
            }
            if tools:
                body["tools"] = [tool_to_openrouter(t) for t in tools]
                body["tool_choice"] = "auto"

            # Retry up to 3 times on rate limits or transient upstream errors
            max_attempts = 3
            backoff = 2.0  # seconds
            response = None
            data = None
            choice = None
            start = time.perf_counter()

            for attempt in range(1, max_attempts + 1):
                start = time.perf_counter()
                try:
                    response = await self._client.post("/chat/completions", json=body)
                except httpx.TimeoutException as exc:
                    raise LLMTimeoutError("OpenRouter request timed out") from exc
                except httpx.HTTPError as exc:
                    raise LLMConnectionError("Failed to reach OpenRouter") from exc

                if response.status_code == 401:
                    raise LLMAuthError("OpenRouter rejected the configured API key (401).")
                if response.status_code == 404:
                    raise LLMModelUnavailableError(f"OpenRouter model '{self._model}' was not found (404).")
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait = float(retry_after) if retry_after else backoff * attempt
                    if attempt < max_attempts:
                        logger.warning(
                            "openrouter_rate_limited_retrying",
                            extra={
                                "event": "openrouter_rate_limited_retrying",
                                "attempt": attempt,
                                "wait_seconds": wait,
                                "model": self._model,
                            },
                        )
                        import asyncio
                        await asyncio.sleep(wait)
                        continue
                    raise LLMRateLimitError("OpenRouter rate limit exceeded (429).")
                if response.status_code >= 500:
                    if attempt < max_attempts:
                        import asyncio
                        logger.warning(
                            "openrouter_upstream_error_retrying",
                            extra={
                                "event": "openrouter_upstream_error_retrying",
                                "attempt": attempt,
                                "status_code": response.status_code,
                                "model": self._model,
                            },
                        )
                        await asyncio.sleep(backoff * attempt)
                        continue
                    raise LLMConnectionError(
                        f"OpenRouter returned {response.status_code}: {response.text[:200]}"
                    )
                if response.status_code >= 400:
                    raise LLMConnectionError(
                        f"OpenRouter returned {response.status_code}: {response.text[:200]}"
                    )

                try:
                    data = response.json()
                except json.JSONDecodeError as exc:
                    raise LLMResponseError(f"OpenRouter returned invalid JSON: {exc}") from exc

                if "error" in data:
                    err_msg = str(data["error"].get("message") if isinstance(data["error"], dict) else data["error"])
                    if attempt < max_attempts and any(k in err_msg.lower() for k in ["overloaded", "rate limit", "busy", "capacity", "502", "503"]):
                        import asyncio
                        logger.warning(
                            "openrouter_embedded_error_retrying",
                            extra={
                                "event": "openrouter_embedded_error_retrying",
                                "attempt": attempt,
                                "error_message": err_msg,
                                "model": self._model,
                            },
                        )
                        await asyncio.sleep(backoff * attempt)
                        continue
                    raise LLMResponseError(f"OpenRouter returned error payload: {err_msg}")

                try:
                    choice = data["choices"][0]
                    raw_message = choice["message"]
                    usage_raw = data.get("usage", {}) or {}
                except (KeyError, IndexError) as exc:
                    raise LLMResponseError(f"Unexpected OpenRouter response shape: {exc}") from exc

                # Success — exit retry loop
                break

            latency_ms = round((time.perf_counter() - start) * 1000, 2)

            message = ChatMessage(
                role=ChatRole.assistant,
                content=raw_message.get("content"),
                tool_calls=parse_tool_calls(raw_message.get("tool_calls")),
            )

            usage = LLMUsage(
                prompt_tokens=usage_raw.get("prompt_tokens", 0),
                completion_tokens=usage_raw.get("completion_tokens", 0),
                total_tokens=usage_raw.get("total_tokens", 0),
            )

            logger.info(
                "openrouter_chat_completed",
                extra={
                    "event": "openrouter_chat_completed",
                    "model": self._model,
                    "latency_ms": latency_ms,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "finish_reason": choice.get("finish_reason"),
                    "tool_call_count": len(message.tool_calls or []),
                },
            )

            return LLMResponse(
                message=message,
                usage=usage,
                model=data.get("model", self._model),
                finish_reason=choice.get("finish_reason"),
                latency_ms=latency_ms,
            )

