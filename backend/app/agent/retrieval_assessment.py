"""Heuristic evidence-sufficiency signals surfaced to the LLM after a
RAG search, so it has more to reason with than raw scores buried in a
JSON blob. This does NOT decide for the LLM whether to retrieve again —
the system prompt already establishes retrieval is iterative and the
LLM retains judgment — it just makes the signal legible in plain
language, attached to the tool result itself.

Deliberately simple, heuristic thresholds — not a learned/tuned quality
model. The project spec explicitly warns against over-engineering this
loop; these thresholds are a reasonable starting point for a portfolio
project, not something the Phase 12 evaluation harness should treat as
ground truth without checking against real results.

Dependency-free — see `backend/tests/test_retrieval_assessment.py`,
which actually runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

# Cross-encoder relevance scores below this are treated as weak
# evidence. Chosen as a starting heuristic, not derived from evaluation
# data (Phase 12 doesn't exist yet) — revisit once real eval numbers
# exist.
LOW_SCORE_THRESHOLD = 0.15


@dataclass(frozen=True)
class RetrievalAssessment:
    result_count: int
    top_score: float
    distinct_documents: int
    is_empty: bool
    is_weak: bool
    note: str


def assess_search_result(search_result: Dict[str, Any]) -> RetrievalAssessment:
    results: List[Dict[str, Any]] = search_result.get("results", []) or []
    result_count = len(results)

    if result_count == 0:
        return RetrievalAssessment(
            result_count=0,
            top_score=0.0,
            distinct_documents=0,
            is_empty=True,
            is_weak=True,
            note=(
                "No matching evidence was found. Consider rewriting the query with different "
                "terms, or concluding the knowledge base doesn't cover this."
            ),
        )

    scores = [float(r.get("score", 0.0)) for r in results]
    top_score = max(scores)
    distinct_documents = len({r.get("document_id") for r in results if r.get("document_id")})
    is_weak = top_score < LOW_SCORE_THRESHOLD

    if is_weak:
        note = (
            f"The top result's relevance score ({top_score:.3f}) is low. This evidence may not "
            "actually answer the question — consider a more specific or differently-phrased "
            "query before relying on it."
        )
    else:
        note = f"Found {result_count} result(s) across {distinct_documents} document(s); top score {top_score:.3f}."

    return RetrievalAssessment(
        result_count=result_count,
        top_score=top_score,
        distinct_documents=distinct_documents,
        is_empty=False,
        is_weak=is_weak,
        note=note,
    )
