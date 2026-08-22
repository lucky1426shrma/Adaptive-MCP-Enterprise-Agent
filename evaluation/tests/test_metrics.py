from __future__ import annotations

from metrics import (
    citation_validity_rate,
    extract_cited_chunk_ids,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)


# --- recall_at_k ---


def test_recall_perfect_when_all_relevant_found() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "b"}, k=3) == 1.0


def test_recall_partial_when_some_relevant_found() -> None:
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, k=3) == 0.5


def test_recall_zero_when_none_found() -> None:
    assert recall_at_k(["x", "y"], {"a", "b"}, k=3) == 0.0


def test_recall_respects_k_cutoff() -> None:
    # "b" is relevant but outside the top-1 cutoff.
    assert recall_at_k(["a", "b"], {"a", "b"}, k=1) == 0.5


def test_recall_empty_relevant_set_scores_perfect() -> None:
    # Deliberately-unanswerable query: nothing relevant exists, so
    # finding nothing to retrieve is correct, not a miss.
    assert recall_at_k(["a", "b"], set(), k=3) == 1.0
    assert recall_at_k([], set(), k=3) == 1.0


# --- precision_at_k ---


def test_precision_perfect_when_all_retrieved_relevant() -> None:
    assert precision_at_k(["a", "b"], {"a", "b", "c"}, k=2) == 1.0


def test_precision_partial() -> None:
    assert precision_at_k(["a", "x"], {"a", "b"}, k=2) == 0.5


def test_precision_zero_for_empty_retrieved_list() -> None:
    assert precision_at_k([], {"a", "b"}, k=5) == 0.0


def test_precision_zero_for_empty_relevant_set_with_nonempty_retrieval() -> None:
    assert precision_at_k(["a", "b"], set(), k=2) == 0.0


def test_precision_respects_k_cutoff() -> None:
    assert precision_at_k(["a", "x", "y"], {"a"}, k=1) == 1.0
    assert precision_at_k(["a", "x", "y"], {"a"}, k=3) == 1.0 / 3


# --- mean_reciprocal_rank ---


def test_mrr_first_result_relevant() -> None:
    assert mean_reciprocal_rank(["a", "x"], {"a"}) == 1.0


def test_mrr_second_result_relevant() -> None:
    assert mean_reciprocal_rank(["x", "a"], {"a"}) == 0.5


def test_mrr_no_relevant_found() -> None:
    assert mean_reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_mrr_empty_relevant_set_scores_perfect() -> None:
    assert mean_reciprocal_rank(["x", "y"], set()) == 1.0


# --- extract_cited_chunk_ids ---


def test_extract_finds_chunk_id_shaped_tokens() -> None:
    text = "This is documented in [march-incident::chunk-2] and also elsewhere."
    assert extract_cited_chunk_ids(text) == ["march-incident::chunk-2"]


def test_extract_finds_multiple() -> None:
    text = "See doc-a::chunk-0 and doc-b::chunk-15 for details."
    assert extract_cited_chunk_ids(text) == ["doc-a::chunk-0", "doc-b::chunk-15"]


def test_extract_returns_empty_for_ordinary_prose() -> None:
    text = "The payment gateway timed out due to a connection pool issue, per the March postmortem."
    assert extract_cited_chunk_ids(text) == []


# --- citation_validity_rate ---


def test_citation_validity_none_when_no_citations_found() -> None:
    assert citation_validity_rate("Ordinary prose with no chunk citations.", {"a::chunk-0"}) is None


def test_citation_validity_all_valid() -> None:
    text = "See [a::chunk-0] and [b::chunk-1]."
    assert citation_validity_rate(text, {"a::chunk-0", "b::chunk-1"}) == 1.0


def test_citation_validity_partial() -> None:
    text = "See [a::chunk-0] and [fabricated::chunk-99]."
    assert citation_validity_rate(text, {"a::chunk-0"}) == 0.5


def test_citation_validity_all_invalid() -> None:
    text = "See [fabricated::chunk-0]."
    assert citation_validity_rate(text, {"a::chunk-0"}) == 0.0
