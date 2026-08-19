"""Cross-encoder reranking — the final precision step of hybrid retrieval.

Kept behind the `Reranker` interface so the reranking model can be
evaluated and swapped independently of the rest of the pipeline. Per
the project spec, reranking effectiveness should be *measured* in the
evaluation phase, not assumed — this abstraction is what makes an A/B
(with-reranker vs without) evaluation straightforward later.
"""

from __future__ import annotations

import abc
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)


class Reranker(abc.ABC):
    """Scores (chunk_id, text) candidates against a query."""

    @abc.abstractmethod
    def rerank(self, query: str, candidates: List[Tuple[str, str]]) -> List[Tuple[str, float]]:
        """Return (chunk_id, score) pairs in the SAME order as `candidates`.

        Callers are responsible for sorting by score — this stays a pure
        scoring function so it's trivial to test and to swap models.
        """
        raise NotImplementedError


class CrossEncoderReranker(Reranker):
    """Local, free, open-source cross-encoder reranker.

    Uses `cross-encoder/ms-marco-MiniLM-L-6-v2` via `sentence-transformers`'
    `CrossEncoder` — a small, widely used, locally runnable reranking
    model. Like the embedding model, this requires a one-time weight
    download from the Hugging Face Hub; all inference after that is
    fully local with no API calls.
    """

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "sentence-transformers is required for CrossEncoderReranker. "
                "Install it via `pip install sentence-transformers`."
            ) from exc

        logger.info(
            "loading_reranker_model",
            extra={"event": "loading_reranker_model", "model": model_name},
        )
        self._model = CrossEncoder(model_name)
        self.model_name = model_name
        logger.info("reranker_model_loaded", extra={"event": "reranker_model_loaded", "model": model_name})

    def rerank(self, query: str, candidates: List[Tuple[str, str]]) -> List[Tuple[str, float]]:
        if not candidates:
            return []
        pairs = [(query, text) for _, text in candidates]
        scores = self._model.predict(pairs)
        return [(chunk_id, float(score)) for (chunk_id, _), score in zip(candidates, scores)]
