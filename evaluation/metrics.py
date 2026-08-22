"""Pure evaluation metrics — dependency-free (stdlib only), so they're
directly unit testable without needing httpx or a running backend. The
actual eval scripts (`run_retrieval_eval.py`, `run_agent_eval.py`,
`run_baseline_vs_agentic.py`) import these; none of them define scoring
logic inline.
"""

from __future__ import annotations

import re
from typing import List, Optional, Sequence, Set

_CHUNK_ID_PATTERN = re.compile(r"[a-zA-Z0-9_.\-]+::chunk-\d+")


def recall_at_k(retrieved_document_ids: Sequence[str], relevant_document_ids: Set[str], k: int) -> float:
    """Fraction of relevant documents that appear anywhere in the top-k
    retrieved results.

    Returns 1.0 if `relevant_document_ids` is empty. This matters for
    deliberately-unanswerable eval queries (see
    evaluation/datasets/rag_eval_seed.jsonl's `rag-010`, whose
    `relevant_document_ids` is `[]`): an empty relevant set means
    "correctly finding nothing to retrieve," which should score
    perfectly, not be penalized as a miss.
    """
    if not relevant_document_ids:
        return 1.0
    top_k = set(retrieved_document_ids[:k])
    found = relevant_document_ids & top_k
    return len(found) / len(relevant_document_ids)


def precision_at_k(retrieved_document_ids: Sequence[str], relevant_document_ids: Set[str], k: int) -> float:
    """Fraction of the top-k retrieved results that are actually relevant.

    Returns 0.0 for an empty retrieved list (nothing retrieved, so
    nothing was precisely relevant) — unlike `recall_at_k`, an empty
    relevant SET doesn't get special-cased here, because precision asks
    "how good were the results," and an empty relevant set with any
    non-empty retrieved list is, definitionally, 0% precision.
    """
    top_k = list(retrieved_document_ids[:k])
    if not top_k:
        return 0.0
    relevant_count = sum(1 for doc_id in top_k if doc_id in relevant_document_ids)
    return relevant_count / len(top_k)


def mean_reciprocal_rank(retrieved_document_ids: Sequence[str], relevant_document_ids: Set[str]) -> float:
    """1/rank of the first relevant result found; 0.0 if none found.

    Returns 1.0 for an empty relevant set, same rationale as
    `recall_at_k`.
    """
    if not relevant_document_ids:
        return 1.0
    for rank, doc_id in enumerate(retrieved_document_ids, start=1):
        if doc_id in relevant_document_ids:
            return 1.0 / rank
    return 0.0


def extract_cited_chunk_ids(answer_text: str) -> List[str]:
    """Extract citation-shaped tokens (`document_id::chunk-N` — this
    project's actual chunk_id format, see
    `services/rag-mcp/app/chunking.py`) from free-form answer text.

    Most real answers WON'T contain tokens in this exact form — the
    system prompt (`backend/app/agent/prompts.py`) asks the model to
    cite by document title, date range, or commit SHA in prose, not by
    raw chunk ID — so an empty result here is the expected common case,
    not itself a problem. See `citation_validity_rate` for how this is
    used.
    """
    return _CHUNK_ID_PATTERN.findall(answer_text)


def citation_validity_rate(answer_text: str, evidence_chunk_ids: Set[str]) -> Optional[float]:
    """Of the chunk-ID-shaped citations found in `answer_text`, what
    fraction correspond to real evidence the agent actually retrieved
    (i.e. appear in `evidence_chunk_ids`)?

    Returns `None` — not `0.0` — if no chunk-ID-shaped citations were
    found in the text at all. "No explicit chunk-ID citations" and
    "citations found but all invalid" are different, not-to-be-confused
    conditions; conflating them into a single float would misrepresent
    the metric. Callers should treat `None` as "not applicable to this
    answer," not as a failure or a zero score.

    NOTE ON SCOPE: this checks citation EXISTENCE validity (does the
    cited chunk actually exist in the evidence the agent gathered), not
    full factual entailment (does the answer's claim actually follow
    from that chunk's text). The latter is "unsupported claim rate" in
    the project spec's metric list and would need an NLP entailment
    model or an LLM-as-judge — deliberately not built here; see
    evaluation/README.md for why that line was drawn.
    """
    cited = extract_cited_chunk_ids(answer_text)
    if not cited:
        return None
    valid = sum(1 for chunk_id in cited if chunk_id in evidence_chunk_ids)
    return valid / len(cited)
