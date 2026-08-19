"""Builds and holds the initialized retrieval pipeline.

Loading the embedding model and reranker is expensive (model weight
load) and both are stateless/thread-safe for inference, so they're
built once here at server startup (see `server.py`'s lifespan) rather
than per-request.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.config import Settings
from app.embeddings import BGEEmbeddingProvider, EmbeddingProvider
from app.reranker import CrossEncoderReranker, Reranker
from app.retrieval import RetrievalPipeline
from app.sparse_index import BM25SparseIndex
from app.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


def _load_chunks(path: Path) -> Tuple[Dict[str, dict], List[str], List[str]]:
    """Load the chunk corpus written by `scripts/ingest.py`.

    Returns (chunk_id -> full record, chunk_ids in file order, texts in
    the same order) — the latter two feed BM25 index construction.
    """
    if not path.exists():
        logger.warning(
            "chunks_index_missing",
            extra={"event": "chunks_index_missing", "path": str(path)},
        )
        return {}, [], []

    chunk_metadata: Dict[str, dict] = {}
    chunk_ids: List[str] = []
    texts: List[str] = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            chunk_metadata[record["chunk_id"]] = record
            chunk_ids.append(record["chunk_id"])
            texts.append(record["text"])

    return chunk_metadata, chunk_ids, texts


class RagContainer:
    """Holds the initialized retrieval pipeline and its components."""

    def __init__(self) -> None:
        self.embedding_provider: Optional[EmbeddingProvider] = None
        self.reranker: Optional[Reranker] = None
        self.vector_store: Optional[QdrantVectorStore] = None
        self.sparse_index: Optional[BM25SparseIndex] = None
        self.pipeline: Optional[RetrievalPipeline] = None
        self.ready: bool = False

    def initialize(self, settings: Settings) -> None:
        logger.info("rag_pipeline_initializing", extra={"event": "rag_pipeline_initializing"})

        self.embedding_provider = BGEEmbeddingProvider(settings.embedding_model)

        self.vector_store = QdrantVectorStore(
            collection_name=settings.qdrant_collection,
            vector_size=self.embedding_provider.dimension,
            url=settings.qdrant_url,
            local_path=settings.qdrant_local_path,
        )

        chunk_metadata, chunk_ids, texts = _load_chunks(settings.chunks_index_path)
        self.sparse_index = BM25SparseIndex(chunk_ids=chunk_ids, texts=texts)

        self.reranker = CrossEncoderReranker(settings.reranker_model) if settings.enable_reranker else None

        self.pipeline = RetrievalPipeline(
            embedding_provider=self.embedding_provider,
            vector_store=self.vector_store,
            sparse_index=self.sparse_index,
            reranker=self.reranker,
            chunk_metadata=chunk_metadata,
            dense_k=settings.dense_k,
            sparse_k=settings.sparse_k,
            rerank_pool_size=settings.rerank_pool_size,
            rrf_k=settings.rrf_k,
        )

        self.ready = True
        logger.info(
            "rag_pipeline_ready",
            extra={
                "event": "rag_pipeline_ready",
                "chunk_count": len(chunk_ids),
                "vector_count": self.vector_store.count(),
                "reranker_enabled": self.reranker is not None,
            },
        )


# Process-wide singleton, populated by server.py's lifespan on startup.
container = RagContainer()
