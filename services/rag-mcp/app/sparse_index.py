"""In-memory BM25 lexical index — the sparse half of hybrid retrieval.

Complements dense retrieval: BM25 is strong on exact keyword/identifier
matches (error codes, service names, ticket IDs) that a dense embedding
model can under-weight. Built from the same chunk corpus produced during
ingestion (`data/index/chunks.jsonl`), independent of Qdrant, so it has
no runtime dependency on the vector store being reachable.
"""

from __future__ import annotations

import logging
import re
from typing import List, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25SparseIndex:
    """Lexical (BM25) search over the ingested chunk corpus."""

    def __init__(self, chunk_ids: List[str], texts: List[str]) -> None:
        if len(chunk_ids) != len(texts):
            raise ValueError("chunk_ids and texts must be the same length")

        self._chunk_ids = chunk_ids
        tokenized_corpus = [_tokenize(t) for t in texts]
        self._bm25 = BM25Okapi(tokenized_corpus) if texts else None

        logger.info(
            "bm25_index_built",
            extra={"event": "bm25_index_built", "chunk_count": len(texts)},
        )

    def search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        """Return up to `top_k` (chunk_id, score) pairs, best first.

        Zero-score matches are dropped — BM25 returning 0 means no
        query terms matched that document at all, which shouldn't count
        as a "sparse hit" for fusion purposes.
        """
        if self._bm25 is None:
            return []

        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self._chunk_ids, scores), key=lambda pair: pair[1], reverse=True)
        return [(chunk_id, float(score)) for chunk_id, score in ranked[:top_k] if score > 0]
