"""Result fusion for hybrid retrieval.

Dependency-free (stdlib only) so it's trivially unit testable.
"""

from __future__ import annotations

from typing import Dict, Hashable, List, Sequence, Tuple, TypeVar

T = TypeVar("T", bound=Hashable)


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[T]],
    k: int = 60,
) -> List[Tuple[T, float]]:
    """Combine multiple ranked lists into one fused ranking via RRF.

    For each item, its RRF score is the sum, over every ranked list it
    appears in, of `1 / (k + rank)` where `rank` is its 1-indexed
    position in that list. Items absent from a list simply don't gain
    a term from it — there's no explicit penalty beyond not contributing.

    `k` is RRF's smoothing constant; 60 is the value used in the
    original RRF paper and is a reasonable default that dampens the
    influence of rank differences far down long lists. This method is
    used (rather than e.g. simple score averaging) because dense
    similarity scores and BM25 scores are on incomparable scales — RRF
    only needs rank order from each source, not calibrated scores.

    Args:
        ranked_lists: one or more sequences of items, each already
            ordered best-to-worst by that retrieval method.
        k: RRF smoothing constant, must be positive.

    Returns:
        (item, fused_score) pairs, deduplicated, sorted by fused score
        descending.

    Raises:
        ValueError: if `k` <= 0.
    """
    if k <= 0:
        raise ValueError("k must be positive")

    scores: Dict[T, float] = {}
    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)

    return sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
