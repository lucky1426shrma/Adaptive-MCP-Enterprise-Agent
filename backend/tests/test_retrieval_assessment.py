from __future__ import annotations

from app.agent.retrieval_assessment import assess_search_result


def test_empty_results_flagged_as_empty_and_weak() -> None:
    assessment = assess_search_result({"results": []})
    assert assessment.is_empty is True
    assert assessment.is_weak is True
    assert assessment.result_count == 0
    assert "no matching evidence" in assessment.note.lower()


def test_missing_results_key_treated_as_empty() -> None:
    assessment = assess_search_result({})
    assert assessment.is_empty is True


def test_high_score_results_not_flagged_weak() -> None:
    result = {"results": [{"document_id": "d1", "score": 0.8}, {"document_id": "d2", "score": 0.6}]}
    assessment = assess_search_result(result)
    assert assessment.is_weak is False
    assert assessment.is_empty is False
    assert assessment.top_score == 0.8
    assert assessment.distinct_documents == 2


def test_low_score_results_flagged_weak() -> None:
    result = {"results": [{"document_id": "d1", "score": 0.05}]}
    assessment = assess_search_result(result)
    assert assessment.is_weak is True
    assert "low" in assessment.note.lower()


def test_distinct_documents_counted_not_result_count() -> None:
    result = {
        "results": [
            {"document_id": "d1", "score": 0.5},
            {"document_id": "d1", "score": 0.4},  # same document, different chunk
            {"document_id": "d2", "score": 0.3},
        ]
    }
    assessment = assess_search_result(result)
    assert assessment.result_count == 3
    assert assessment.distinct_documents == 2


def test_missing_score_defaults_to_zero_and_is_weak() -> None:
    result = {"results": [{"document_id": "d1"}]}
    assessment = assess_search_result(result)
    assert assessment.top_score == 0.0
    assert assessment.is_weak is True
