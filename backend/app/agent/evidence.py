"""Accumulates RAG evidence across one agent run, deduplicated by
chunk_id (keeping the highest score seen for any chunk retrieved more
than once), independent of raw message history.

This is what grounds "evidence synthesis": the final answer is written
with a clean structured evidence summary in context, not by the LLM
re-parsing raw tool-result JSON scattered through the conversation
(which also degrades gracefully if that history ever gets truncated in
a future phase — the evidence store doesn't depend on message history
staying intact).

Evidence is stored as plain dicts (not a dataclass) because it lives in
`AgentState` (a `TypedDict`, see `graph.py`) via a custom LangGraph
reducer (`merge_evidence_items`) — keeping it plain data avoids mixing
object identity semantics into state that LangGraph copies/merges.

Deliberately dependency-free (stdlib only) — see
`backend/tests/test_evidence.py`, which actually runs.
"""

from __future__ import annotations

from typing import Any, Dict, List


def extract_evidence_items(search_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull well-formed evidence dicts out of a `search_knowledge` tool
    result. Malformed entries (missing fields, non-numeric score) are
    skipped rather than raising — one bad entry shouldn't lose the rest
    of an otherwise-good result.
    """
    items: List[Dict[str, Any]] = []
    for r in search_result.get("results", []) or []:
        try:
            items.append(
                {
                    "chunk_id": r["chunk_id"],
                    "document_id": r["document_id"],
                    "title": r["title"],
                    "source": r["source"],
                    "text": r["text"],
                    "score": float(r.get("score", 0.0)),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return items


def merge_evidence_items(
    existing: List[Dict[str, Any]], new: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """LangGraph state reducer for `AgentState.evidence_items`.

    Merges newly-extracted evidence into the existing accumulated set,
    deduplicated by `chunk_id`, keeping whichever version scored higher
    (the same chunk can come back with a different score across
    differently-worded queries). Result is sorted by score, descending,
    so the summary text below reads best-evidence-first.
    """
    by_id: Dict[str, Dict[str, Any]] = {item["chunk_id"]: item for item in existing}
    for item in new:
        current = by_id.get(item["chunk_id"])
        if current is None or item.get("score", 0.0) > current.get("score", 0.0):
            by_id[item["chunk_id"]] = item
    return sorted(by_id.values(), key=lambda i: i.get("score", 0.0), reverse=True)


def evidence_summary_text(evidence_items: List[Dict[str, Any]], snippet_chars: int = 200) -> str:
    """Human-readable evidence summary injected into the LLM's context
    ahead of each turn once evidence exists — see `nodes.py`."""
    if not evidence_items:
        return "No evidence has been retrieved from the knowledge base yet."

    document_ids: List[str] = []
    for item in evidence_items:
        if item["document_id"] not in document_ids:
            document_ids.append(item["document_id"])

    lines = [f"Accumulated evidence from {len(document_ids)} document(s):"]
    for item in evidence_items:
        snippet = item["text"][:snippet_chars]
        lines.append(f'- [{item["chunk_id"]}] "{item["title"]}" (score={item["score"]:.3f}): {snippet}')
    return "\n".join(lines)
