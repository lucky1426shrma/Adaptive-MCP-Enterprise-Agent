"""Wires `app/agent/nodes.py` functions into a LangGraph `StateGraph`.

This module contains NO business logic of its own — see
`app/agent/nodes.py`, which is deliberately dependency-free and unit
tested directly (`backend/tests/test_agent_nodes.py`). This module's
only job is graph topology: agent -> (tools -> agent)* -> end, with a
force_stop escape hatch when the iteration cap is hit.

Phase 8 (agentic RAG) added two state fields — `evidence_items` and
`rag_queries_used` — threaded through the same three nodes; Phase 12
added token-usage accounting (`prompt_tokens`/`completion_tokens`/
`total_tokens`, simple additive reducers). The graph topology itself
is UNCHANGED from Phase 7 through every subsequent phase, per the
project spec's "layer on the same graph, don't rewrite it" guidance.

VERIFICATION NOTE: `langgraph.graph.StateGraph` / `add_node` /
`add_conditional_edges` / `set_entry_point` / `compile()` / `END` are
LangGraph's core, stable public API — much lower risk than the MCP SDK
internals flagged elsewhere in this project — but this couldn't be
executed in the environment this was built in (no network to install
`langgraph`). Verify with `pytest -v` locally; if the graph fails to
compile, check the installed `langgraph` version's `StateGraph` docs
first.
"""

from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Annotated, Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agent.evidence import merge_evidence_items
from app.agent.nodes import run_agent_node, run_force_stop_node, run_tools_node, should_continue
from app.agent.tool_catalog import ToolCatalog
from app.llm.provider import LLMProvider
from app.llm.schemas import ChatMessage

if TYPE_CHECKING:
    from app.mcp.registry import MCPRegistry


class AgentState(TypedDict):
    messages: Annotated[List[ChatMessage], operator.add]
    iterations: int
    tool_calls_made: Annotated[List[Dict[str, Any]], operator.add]
    # Phase 8: accumulated RAG evidence, deduplicated by chunk_id via a
    # custom reducer (not plain append — see app/agent/evidence.py).
    evidence_items: Annotated[List[Dict[str, Any]], merge_evidence_items]
    # Phase 8: every query string sent to rag__search_knowledge, in
    # order, across the whole run — plain append; duplicates are
    # meaningful signal here (see app/agent/rag_loop_guard.py), not
    # noise to be deduplicated away.
    rag_queries_used: Annotated[List[str], operator.add]
    # Phase 12: accumulated LLM token usage across every LLM turn this
    # run made (agent_node calls plus a possible force_stop call) — a
    # simple running sum, since token counts across turns are
    # genuinely additive (unlike evidence, there's no "same item twice"
    # concept to deduplicate).
    prompt_tokens: Annotated[int, operator.add]
    completion_tokens: Annotated[int, operator.add]
    total_tokens: Annotated[int, operator.add]
    error: Optional[str]


def build_agent_graph(
    llm_provider: LLMProvider,
    registry: "MCPRegistry",
    catalog: ToolCatalog,
    max_iterations: int,
    rag_max_retrieval_attempts: int,
):
    async def agent_node(state: AgentState) -> Dict[str, Any]:
        return await run_agent_node(
            state["messages"], state["iterations"], llm_provider, catalog, state["evidence_items"]
        )

    async def tools_node(state: AgentState) -> Dict[str, Any]:
        return await run_tools_node(
            state["messages"][-1], registry, catalog, state["rag_queries_used"], rag_max_retrieval_attempts
        )

    async def force_stop_node(state: AgentState) -> Dict[str, Any]:
        return await run_force_stop_node(
            state["messages"], state["iterations"], llm_provider, state.get("error"), state["evidence_items"]
        )

    def _route(state: AgentState) -> str:
        return should_continue(state["messages"][-1], state["iterations"], max_iterations)

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("force_stop", force_stop_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges(
        "agent", _route, {"tools": "tools", "end": END, "force_stop": "force_stop"}
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("force_stop", END)

    return graph.compile()
