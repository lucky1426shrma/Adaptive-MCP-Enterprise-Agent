"""Pure helpers for bounding and nudging the RAG-specific retrieval
loop: a call budget independent of the general LLM-turn cap
(`llm_max_tool_iterations`), and detection of verbatim-repeated queries
so the LLM gets nudged toward actually rewriting rather than retrying
identical input.

Deliberately simple — exact-string (case/whitespace-insensitive) repeat
detection, a hard count cap — per the project spec's explicit warning
against over-engineering this loop with anything fancier.

Dependency-free — see `backend/tests/test_rag_loop_guard.py`, which
actually runs.
"""

from __future__ import annotations

from typing import List


def rag_attempts_remaining(queries_used: List[str], max_attempts: int) -> int:
    return max(0, max_attempts - len(queries_used))


def is_repeat_query(query: str, queries_used: List[str]) -> bool:
    normalized = query.strip().lower()
    return any(normalized == q.strip().lower() for q in queries_used)
