from __future__ import annotations

import pytest

from app.fusion import reciprocal_rank_fusion


def test_single_list_preserves_order() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"]])
    assert [item for item, _ in fused] == ["a", "b", "c"]


def test_item_ranked_first_in_both_lists_wins() -> None:
    dense = ["a", "b", "c"]
    sparse = ["a", "c", "b"]
    fused = reciprocal_rank_fusion([dense, sparse])
    assert fused[0][0] == "a"


def test_item_appearing_in_both_lists_outranks_item_in_only_one() -> None:
    # "b" is #1 in dense only. "c" is #2 in both dense and sparse.
    dense = ["b", "c"]
    sparse = ["c", "d"]
    fused = reciprocal_rank_fusion([dense, sparse])
    fused_scores = dict(fused)
    assert fused_scores["c"] > fused_scores["b"]


def test_item_missing_from_a_list_still_scores_from_the_other() -> None:
    dense = ["a", "b"]
    sparse: list = []
    fused = reciprocal_rank_fusion([dense, sparse])
    fused_ids = [item for item, _ in fused]
    assert fused_ids == ["a", "b"]


def test_results_sorted_descending_by_score() -> None:
    fused = reciprocal_rank_fusion([["x", "y", "z"], ["z", "x", "y"]])
    scores = [score for _, score in fused]
    assert scores == sorted(scores, reverse=True)


def test_empty_input_returns_empty_list() -> None:
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_deduplicates_items_across_lists() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["a", "c"]])
    ids = [item for item, _ in fused]
    assert len(ids) == len(set(ids)) == 3


def test_larger_k_flattens_score_differences() -> None:
    ranked = ["a", "b", "c"]
    fused_small_k = dict(reciprocal_rank_fusion([ranked], k=1))
    fused_large_k = dict(reciprocal_rank_fusion([ranked], k=1000))

    gap_small_k = fused_small_k["a"] - fused_small_k["c"]
    gap_large_k = fused_large_k["a"] - fused_large_k["c"]
    assert gap_small_k > gap_large_k


def test_invalid_k_raises_value_error() -> None:
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=0)
    with pytest.raises(ValueError):
        reciprocal_rank_fusion([["a"]], k=-10)
