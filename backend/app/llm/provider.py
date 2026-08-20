"""Abstract LLM provider interface.

LangGraph, the agent nodes, and the rest of the application depend
ONLY on this interface — never on OpenRouter-specific request/response
shapes. `app/llm/openrouter_provider.py` is the one concrete
implementation. This is what lets the provider be swapped later
without touching the agent graph, MCP client, or FastAPI layer, per
the project's provider-abstraction requirement:

    LangGraph Agent -> LLMProvider -> OpenRouterProvider -> OpenRouter API
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from app.llm.schemas import ChatMessage, LLMResponse, ToolDefinition


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self, messages: List[ChatMessage], tools: Optional[List[ToolDefinition]] = None
    ) -> LLMResponse:
        """Send a chat completion request, optionally offering tools the
        model may choose to call.

        Must raise a subclass of `app.llm.exceptions.LLMProviderError` on
        any failure — never let a provider-specific exception (e.g. an
        `httpx` exception) leak past this interface.
        """
        raise NotImplementedError
