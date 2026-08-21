"""Agent graph node logic — deliberately separate from `graph.py` so
this can be unit tested with fake LLM providers / MCP registries
WITHOUT `langgraph` installed. `graph.py` imports these functions and
wires them into a `StateGraph`; it contains no business logic of its
own. See `backend/tests/test_agent_nodes.py`, which actually runs
against fakes.

Phase 8 (agentic RAG) additions live here as small, focused steps
layered onto the same three nodes rather than new graph topology:
evidence accumulation (`app/agent/evidence.py`), per-result
sufficiency assessment (`app/agent/retrieval_assessment.py`), and a
RAG-specific retrieval budget / repeat-query nudge
(`app/agent/rag_loop_guard.py`) — all still dependency-free, all still
directly unit tested.

Phase 9 added defense-in-depth prompt-injection detection
(`app/agent/injection_detection.py`), also dependency-free.

Phase 10 added tracing spans via `app/observability/span_helper.py`,
whose `start_span()` is a no-op when `opentelemetry` isn't installed —
that's what lets spans live in this module without it acquiring a hard
dependency on the `opentelemetry` package. This module's zero-hard-
dependency property (on `mcp`/`httpx`/`langgraph`/`opentelemetry`) is
deliberate and load-bearing: it's what makes 30+ tests in
`test_agent_nodes.py` runnable without installing the full stack.

Phase 12 added token-usage accounting (`prompt_tokens`/
`completion_tokens`/`total_tokens` in each successful LLM-turn's
return dict), threaded through to `AgentState` via simple additive
reducers in `graph.py`, so the evaluation harness can report real
token usage per agent run — previously computed internally by
`LLMResponse.usage` but never surfaced past the LLM provider layer.

`MCPRegistry` is imported only under `TYPE_CHECKING` for the same
reason.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from app.agent.evidence import evidence_summary_text, extract_evidence_items
from app.agent.injection_detection import INJECTION_WARNING_BANNER, detect_injection_patterns
from app.agent.rag_loop_guard import is_repeat_query, rag_attempts_remaining
from app.agent.retrieval_assessment import assess_search_result
from app.agent.tool_catalog import ToolCatalog
from app.llm.exceptions import LLMProviderError
from app.llm.provider import LLMProvider
from app.llm.schemas import ChatMessage, ChatRole
from app.observability.span_helper import start_span

if TYPE_CHECKING:
    from app.mcp.registry import MCPRegistry

logger = logging.getLogger(__name__)

# The tool this RAG-specific loop logic applies to, post-resolution
# (server_name, real_tool_name) — matches services/rag-mcp's actual
# tool name. If a second RAG-like tool is ever added, extend this
# check rather than generalizing prematurely (YAGNI).
_RAG_SEARCH_TOOL = ("rag", "search_knowledge")


async def run_agent_node(
    messages: List[ChatMessage],
    iterations: int,
    llm_provider: LLMProvider,
    catalog: ToolCatalog,
    evidence_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """One LLM turn: given the conversation so far, either produce tool
    calls or a final answer. On LLM failure, degrades to a user-facing
    apology rather than raising — an LLM outage should end the graph
    gracefully, not crash the request.

    If evidence has been accumulated (Phase 8), an up-to-date summary
    is injected into the system context for this call only — it is not
    added to `messages` in the returned state, so it doesn't bloat or
    duplicate conversation history turn over turn; it's regenerated fresh
    from `evidence_items` every time.
    """
    with start_span(
        "agent.agent_node", {"iterations": iterations, "evidence_item_count": len(evidence_items)}
    ):
        effective_messages = list(messages)
        if evidence_items:
            evidence_block = (
                "\n\nEvidence accumulated so far across all searches this run "
                "(deduplicated, highest-scoring version of each item):\n"
                + evidence_summary_text(evidence_items)
            )
            if effective_messages and effective_messages[0].role == ChatRole.system:
                base_system = effective_messages[0].content or ""
                effective_messages[0] = ChatMessage(
                    role=ChatRole.system,
                    content=base_system + evidence_block,
                )
            else:
                effective_messages.insert(
                    0,
                    ChatMessage(
                        role=ChatRole.system,
                        content="Evidence accumulated so far across all searches this run:\n"
                        + evidence_summary_text(evidence_items),
                    ),
                )

        try:
            response = await llm_provider.chat(effective_messages, tools=catalog.tools or None)
        except LLMProviderError as exc:
            logger.error(
                "agent_llm_call_failed",
                extra={"event": "agent_llm_call_failed", "error_type": type(exc).__name__},
            )
            fallback = ChatMessage(
                role=ChatRole.assistant,
                content=(
                    "I ran into a problem reaching the language model and can't complete this "
                    "request right now. Please try again shortly."
                ),
            )
            return {"messages": [fallback], "error": f"llm_error:{type(exc).__name__}"}

        return {
            "messages": [response.message],
            "iterations": iterations + 1,
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }


async def run_tools_node(
    last_message: ChatMessage,
    registry: "MCPRegistry",
    catalog: ToolCatalog,
    rag_queries_used: List[str],
    rag_max_attempts: int,
) -> Dict[str, Any]:
    """Execute every tool call the LLM requested in `last_message`.

    Each tool call is handled independently: one failing (unknown tool
    name, unavailable server, or an MCP-level error) never blocks the
    others in the same turn, and always produces a tool-result message
    so the LLM sees what happened and can decide what to do next
    (retry differently, try another tool, or answer with what it has).
    Each tool call also gets its own child span, nested under this
    node's span, so a trace shows exactly which calls happened and how
    long each took even when a single LLM turn requests several.

    Phase 8 additions, applied specifically to `rag__search_knowledge`
    calls (identified by `_RAG_SEARCH_TOOL` after resolution, not by
    string-matching the prefixed name, so this stays correct even if
    the server prefix scheme changes):
    - a retrieval budget independent of the general LLM-turn cap: once
      exhausted, further RAG calls this run are short-circuited with a
      clear message instead of hitting the MCP server;
    - a repeat-query nudge appended to the result when the same query
      (case/whitespace-insensitive) was already used this run;
    - a plain-language sufficiency assessment appended to every
      successful result (see `assess_search_result`);
    - extracted evidence items returned for the caller to merge into
      `AgentState.evidence_items` via `merge_evidence_items`.
    """
    tool_calls = last_message.tool_calls or []

    with start_span("agent.tools_node", {"tool_call_count": len(tool_calls)}):
        result_messages: List[ChatMessage] = []
        records: List[Dict[str, Any]] = []
        new_evidence: List[Dict[str, Any]] = []
        new_rag_queries: List[str] = []

        # Local running view of queries used, so a single LLM turn that
        # requests more than one RAG search still has budget/repeat checks
        # applied correctly call-to-call within this same turn.
        queries_so_far = list(rag_queries_used)

        for tool_call in tool_calls:
            with start_span("agent.tool_call", {"tool": tool_call.name}):
                start = time.perf_counter()

                try:
                    route = catalog.resolve(tool_call.name)
                except KeyError:
                    content = json.dumps({"error": f"Unknown tool '{tool_call.name}'."})
                    result_messages.append(
                        ChatMessage(
                            role=ChatRole.tool, tool_call_id=tool_call.id, name=tool_call.name, content=content
                        )
                    )
                    records.append(
                        {"tool": tool_call.name, "server": None, "status": "unknown_tool", "latency_ms": 0.0}
                    )
                    continue

                server_name, real_tool_name = route
                is_rag_search = route == _RAG_SEARCH_TOOL
                query = str(tool_call.arguments.get("query", "")) if is_rag_search else ""
                repeat = is_rag_search and is_repeat_query(query, queries_so_far)

                if is_rag_search and rag_attempts_remaining(queries_so_far, rag_max_attempts) <= 0:
                    content = json.dumps(
                        {
                            "error": (
                                f"The retrieval budget for this request ({rag_max_attempts} searches) "
                                "has been used up. Answer using the evidence already gathered, or state "
                                "that the evidence is insufficient."
                            )
                        }
                    )
                    latency_ms = round((time.perf_counter() - start) * 1000, 2)
                    result_messages.append(
                        ChatMessage(
                            role=ChatRole.tool, tool_call_id=tool_call.id, name=tool_call.name, content=content
                        )
                    )
                    records.append(
                        {
                            "tool": tool_call.name,
                            "server": server_name,
                            "status": "rag_budget_exhausted",
                            "latency_ms": latency_ms,
                        }
                    )
                    continue

                client = registry.get(server_name)
                call_data: Optional[Dict[str, Any]] = None
                if client is None:
                    content = json.dumps({"error": f"MCP server '{server_name}' is not available."})
                    status = "server_unavailable"
                else:
                    try:
                        call_result = await client.call_tool(real_tool_name, tool_call.arguments)
                        call_data = call_result.data
                        content = json.dumps(call_data) if call_data is not None else (call_result.raw_text or "")
                        status = "success"
                    except Exception as exc:  # noqa: BLE001 - any MCP-layer failure must degrade to a tool-result message, not crash the graph
                        logger.warning(
                            "agent_tool_call_failed",
                            extra={
                                "event": "agent_tool_call_failed",
                                "server": server_name,
                                "tool": real_tool_name,
                                "error_type": type(exc).__name__,
                            },
                        )
                        content = json.dumps({"error": f"Tool call failed: {type(exc).__name__}"})
                        status = "error"

                if is_rag_search:
                    queries_so_far.append(query)
                    new_rag_queries.append(query)

                    if status == "success" and call_data is not None:
                        new_evidence.extend(extract_evidence_items(call_data))

                        assessment = assess_search_result(call_data)
                        note = assessment.note
                        if repeat:
                            note += (
                                " Note: this is a repeat of an earlier query in this same request — "
                                "consider rewriting it with different terms if results are still "
                                "insufficient, rather than retrying the same query again."
                            )

                        augmented = dict(call_data)
                        augmented["assessment"] = note
                        content = json.dumps(augmented)

                # Defense-in-depth prompt-injection check (Phase 9): applied to
                # every tool result, not just RAG — GitHub commit messages or
                # DB error fields are smaller but non-zero injection surfaces
                # too. Flags, doesn't block (see injection_detection.py).
                injection_matches = detect_injection_patterns(content)
                if injection_matches:
                    logger.warning(
                        "tool_result_injection_pattern_detected",
                        extra={
                            "event": "tool_result_injection_pattern_detected",
                            "server": server_name,
                            "tool": real_tool_name,
                            "matched_pattern_count": len(injection_matches),
                        },
                    )
                    content = INJECTION_WARNING_BANNER + content

                latency_ms = round((time.perf_counter() - start) * 1000, 2)
                result_messages.append(
                    ChatMessage(role=ChatRole.tool, tool_call_id=tool_call.id, name=tool_call.name, content=content)
                )
                records.append(
                    {"tool": tool_call.name, "server": server_name, "status": status, "latency_ms": latency_ms}
                )

        return {
            "messages": result_messages,
            "tool_calls_made": records,
            "evidence_items": new_evidence,
            "rag_queries_used": new_rag_queries,
        }


async def run_force_stop_node(
    messages: List[ChatMessage],
    iterations: int,
    llm_provider: LLMProvider,
    error: Optional[str],
    evidence_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Stopping-criteria path: the iteration cap was hit while the model
    still wanted more tools. Ask it ONE more time, with tools withheld,
    to synthesize a real answer from whatever evidence was already
    gathered — rather than just returning a canned "I gave up" message.
    Includes the same accumulated-evidence summary as `run_agent_node`
    so the forced final answer is grounded the same way a normal one
    would be.
    """
    with start_span("agent.force_stop_node", {"iterations": iterations}):
        logger.warning(
            "agent_max_iterations_reached",
            extra={"event": "agent_max_iterations_reached", "iterations": iterations},
        )
        effective_messages = list(messages)
        if evidence_items:
            evidence_block = (
                "\n\nEvidence accumulated so far across all searches this run:\n"
                + evidence_summary_text(evidence_items)
            )
            if effective_messages and effective_messages[0].role == ChatRole.system:
                base_system = effective_messages[0].content or ""
                effective_messages[0] = ChatMessage(
                    role=ChatRole.system,
                    content=base_system + evidence_block,
                )
            else:
                effective_messages.insert(
                    0,
                    ChatMessage(
                        role=ChatRole.system,
                        content="Evidence accumulated so far across all searches this run:\n"
                        + evidence_summary_text(evidence_items),
                    ),
                )

        effective_messages.append(
            ChatMessage(
                role=ChatRole.user,
                content=(
                    "You have reached the maximum number of tool calls for this request. "
                    "Answer now using only the evidence already gathered above; do not request "
                    "any further tools. If the evidence so far is insufficient, say so explicitly."
                ),
            )
        )

        try:
            response = await llm_provider.chat(effective_messages, tools=None)
            final_message = response.message
            token_deltas: Dict[str, Any] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        except LLMProviderError:
            final_message = ChatMessage(
                role=ChatRole.assistant,
                content=(
                    "I gathered some evidence but hit the tool-call limit and couldn't reach "
                    "the model to summarize it."
                ),
            )
            token_deltas = {}
        return {
            "messages": [final_message],
            "error": error or "max_iterations_reached",
            **token_deltas,
        }


def should_continue(last_message: ChatMessage, iterations: int, max_iterations: int) -> str:
    """The graph's stopping criteria, as a pure function of the last
    message and iteration count — no state mutation, trivially testable.
    """
    if last_message.role != ChatRole.assistant:
        # Shouldn't happen (tools_node always routes back to agent_node),
        # but fail safe rather than let the graph loop indefinitely.
        return "end"
    if not last_message.tool_calls:
        return "end"
    if iterations >= max_iterations:
        return "force_stop"
    return "tools"
