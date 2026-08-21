"""High-level entrypoint for running the agent on one user question.

`app/api/chat.py` calls `AgentService.run()` — it owns building the
initial state (system prompt + user question), ensuring the tool
catalog is loaded, compiling/running the graph, applying the overall
per-request timeout, and shaping the result into something the API
layer can serialize.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.agent.graph import build_agent_graph
from app.agent.prompts import get_system_prompt
from app.agent.tool_catalog import ToolCatalog, catalog as default_catalog
from app.llm.provider import LLMProvider
from app.llm.schemas import ChatMessage, ChatRole

if TYPE_CHECKING:
    from app.config import Settings
    from app.mcp.registry import MCPRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    answer: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    # Phase 11: surfaces the Phase 8 evidence store (deduplicated,
    # highest-scoring version of each retrieved chunk) so the frontend
    # can render real citations instead of only prose the LLM happened
    # to write — this data already existed in AgentState, it just
    # wasn't threaded out to the API response until now.
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    # Phase 12: accumulated LLM token usage across the whole run —
    # surfaced for the evaluation harness's "token usage" metric.
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    iterations: int = 0
    error: Optional[str] = None
    latency_ms: float = 0.0


class AgentService:
    def __init__(
        self,
        llm_provider: LLMProvider,
        registry: "MCPRegistry",
        max_tool_iterations: int,
        agent_timeout_seconds: float,
        rag_max_retrieval_attempts: int,
        tool_catalog: ToolCatalog = default_catalog,
    ) -> None:
        self._llm = llm_provider
        self._registry = registry
        self._catalog = tool_catalog
        self._agent_timeout_seconds = agent_timeout_seconds
        self._graph = build_agent_graph(
            llm_provider, registry, tool_catalog, max_tool_iterations, rag_max_retrieval_attempts
        )

    async def run(self, question: str) -> AgentRunResult:
        # Refresh if catalog is empty or if any registered MCP server had not loaded yet
        if self._catalog.is_empty or len(self._catalog.loaded_servers) < len(self._registry.all()):
            await self._catalog.refresh(self._registry)

        initial_state = {
            "messages": [
                ChatMessage(role=ChatRole.system, content=get_system_prompt()),
                ChatMessage(role=ChatRole.user, content=question),
            ],
            "iterations": 0,
            "tool_calls_made": [],
            "evidence_items": [],
            "rag_queries_used": [],
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "error": None,
        }

        start = time.perf_counter()
        try:
            async with asyncio.timeout(self._agent_timeout_seconds):
                final_state = await self._graph.ainvoke(initial_state)
        except TimeoutError:
            logger.error(
                "agent_run_timed_out",
                extra={"event": "agent_run_timed_out", "question_length": len(question)},
            )
            return AgentRunResult(
                answer=(
                    "I wasn't able to finish investigating this in time. "
                    "Please try again or narrow the question."
                ),
                error="timeout",
                latency_ms=round((time.perf_counter() - start) * 1000, 2),
            )

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        answer = ""
        # Find the latest assistant message with content
        for msg in reversed(final_state.get("messages", [])):
            if msg.role == ChatRole.assistant and msg.content:
                answer = msg.content
                break
        if not answer:
            last_message = final_state["messages"][-1] if final_state.get("messages") else None
            answer = (last_message.content if last_message and last_message.content else None) or "I wasn't able to produce an answer."

        return AgentRunResult(
            answer=answer,
            tool_calls=final_state.get("tool_calls_made", []),
            evidence=final_state.get("evidence_items", []),
            prompt_tokens=final_state.get("prompt_tokens", 0),
            completion_tokens=final_state.get("completion_tokens", 0),
            total_tokens=final_state.get("total_tokens", 0),
            iterations=final_state.get("iterations", 0),
            error=final_state.get("error"),
            latency_ms=latency_ms,
        )


# Process-wide singleton, set during FastAPI's lifespan startup if
# OpenRouter is configured; left None otherwise (see main.py). None
# means "the agent isn't available" — /chat reports 503, everything
# else in the app keeps working, consistent with how an unconfigured
# MCP server degrades a specific capability rather than the whole app.
_agent_service: Optional[AgentService] = None


def get_agent_service() -> Optional[AgentService]:
    return _agent_service


def set_agent_service(service: Optional[AgentService]) -> None:
    global _agent_service
    _agent_service = service
