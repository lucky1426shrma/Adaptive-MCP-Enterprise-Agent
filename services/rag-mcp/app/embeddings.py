"""Embedding provider abstraction.

Kept behind `EmbeddingProvider` so the concrete model (currently
BAAI/bge-small-en-v1.5, run locally via `sentence-transformers`) can be
replaced later without touching the retrieval pipeline, Qdrant wiring,
or the MCP tool surface. IMPORTANT: if the model is ever changed, the
Qdrant collection must be re-indexed (via `scripts/ingest.py` against a
fresh collection name) — never mix vectors produced by different models
in the same collection.
"""

from __future__ import annotations

import abc
import logging
from typing import List

logger = logging.getLogger(__name__)


class EmbeddingProvider(abc.ABC):
    """Abstraction over the model used to embed text for retrieval."""

    #: Vector dimensionality this provider produces. Must match the
    #: Qdrant collection's configured vector size.
    dimension: int

    @abc.abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embed a batch of document chunks for indexing."""
        raise NotImplementedError

    @abc.abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Embed a single search query."""
        raise NotImplementedError


class BGEEmbeddingProvider(EmbeddingProvider):
    """Local, free, open-source embeddings via BAAI/bge-small-en-v1.5.

    Requires `sentence-transformers` and, on first use, network access
    to download model weights from the Hugging Face Hub (cached locally
    afterward, typically under `~/.cache/huggingface`). All *inference*
    after that first download is local — no external API calls, no
    per-call cost, satisfying the project's zero-cost / no-mandatory-
    external-API constraint.

    BGE models are trained for *asymmetric* retrieval — queries and
    documents are not meant to be embedded identically. Per the model's
    documented usage convention, queries (not documents) are prefixed
    with an instruction string before encoding.

    Note: bge-small-en-v1.5 is English-oriented. If the real corpus is
    multilingual, evaluate a multilingual embedding model before
    swapping this in — don't assume this default generalizes.
    """

    _QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5") -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:  # pragma: no cover - import guard
            raise ImportError(
                "sentence-transformers is required for BGEEmbeddingProvider. "
                "Install it via `pip install sentence-transformers`."
            ) from exc

        logger.info(
            "loading_embedding_model",
            extra={"event": "loading_embedding_model", "model": model_name},
        )
        self._model = SentenceTransformer(model_name)
        self.dimension = self._model.get_sentence_embedding_dimension()
        self.model_name = model_name
        logger.info(
            "embedding_model_loaded",
            extra={"event": "embedding_model_loaded", "model": model_name, "dimension": self.dimension},
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return vectors.tolist()

    def embed_query(self, text: str) -> List[float]:
        prefixed = f"{self._QUERY_INSTRUCTION}{text}"
        vector = self._model.encode([prefixed], normalize_embeddings=True, convert_to_numpy=True)
        return vector[0].tolist()
