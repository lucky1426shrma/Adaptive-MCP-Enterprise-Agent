"""Hybrid retrieval pipeline: dense (Qdrant) + sparse (BM25) -> RRF fusion
-> cross-encoder rerank -> top-K cited evidence.

This module is the SOLE owner of retrieval mechanics for the RAG MCP
server. `server.py`'s `search_knowledge` MCP tool is a thin wrapper
around `RetrievalPipeline.run()` — it does not talk to Qdrant, BM25, or
the reranker directly. That separation is what makes each piece
(chunking, fusion) independently unit-testable without a running
Qdrant/model stack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from app.fusion import reciprocal_rank_fusion
from app.span_helper import start_span

# These are only used as type hints. Importing them lazily (type-checking
# only) means this module — the actual orchestration logic — has no hard
# runtime dependency on qdrant-client / rank_bm25 / sentence-transformers,
# only on `app.fusion` (stdlib-only). That's what makes RetrievalPipeline
# unit-testable with lightweight fakes, without the full model/vector-store
# stack installed. `server.py` and `scripts/ingest.py`, which construct the
# real objects, still need those packages installed.
if TYPE_CHECKING:
    from app.embeddings import EmbeddingProvider
    from app.reranker import Reranker
    from app.sparse_index import BM25SparseIndex
    from app.vector_store import QdrantVectorStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedEvidence:
    chunk_id: str
    document_id: str
    title: str
    source: str
    text: str
    score: float


class RetrievalPipeline:
    """Runs one hybrid-retrieval query end-to-end and returns cited evidence."""

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_store: QdrantVectorStore,
        sparse_index: BM25SparseIndex,
        reranker: Optional[Reranker],
        chunk_metadata: Dict[str, dict],
        dense_k: int = 20,
        sparse_k: int = 20,
        rerank_pool_size: int = 15,
        rrf_k: int = 60,
    ) -> None:
        self._embeddings = embedding_provider
        self._vector_store = vector_store
        self._sparse_index = sparse_index
        self._reranker = reranker
        # chunk_id -> {document_id, title, source, text, ...}
        self._chunk_metadata = chunk_metadata
        self._dense_k = dense_k
        self._sparse_k = sparse_k
        self._rerank_pool_size = rerank_pool_size
        self._rrf_k = rrf_k

    def run(self, query: str, top_k: int) -> Tuple[List[RetrievedEvidence], dict]:
        with start_span("rag.retrieval_pipeline", {"query_length": len(query), "top_k": top_k}):
            # 1. Dense retrieval
            with start_span("rag.dense_search", {"dense_k": self._dense_k}):
                query_vector = self._embeddings.embed_query(query)
                dense_hits = self._vector_store.search(query_vector, top_k=self._dense_k)
                dense_ranked_ids = [hit.payload["chunk_id"] for hit in dense_hits if hit.payload]

            # 2. Sparse (BM25) retrieval
            with start_span("rag.sparse_search", {"sparse_k": self._sparse_k}):
                sparse_hits = self._sparse_index.search(query, top_k=self._sparse_k)
                sparse_ranked_ids = [chunk_id for chunk_id, _ in sparse_hits]

            # 3. Fusion (reciprocal rank fusion over the two rank-ordered ID lists)
            with start_span(
                "rag.fusion",
                {"dense_candidates": len(dense_ranked_ids), "sparse_candidates": len(sparse_ranked_ids)},
            ):
                fused = reciprocal_rank_fusion([dense_ranked_ids, sparse_ranked_ids], k=self._rrf_k)
                pool = fused[: self._rerank_pool_size]

                candidates = [
                    (chunk_id, self._chunk_metadata[chunk_id]["text"])
                    for chunk_id, _ in pool
                    if chunk_id in self._chunk_metadata
                ]

            # 4. Rerank (if enabled) — otherwise fall back to fused RRF order
            with start_span("rag.rerank", {"candidate_count": len(candidates), "reranker_enabled": self._reranker is not None}):
                if self._reranker is not None and candidates:
                    reranked_scores = dict(self._reranker.rerank(query, candidates))
                    ordered_ids = sorted(
                        (cid for cid, _ in candidates),
                        key=lambda cid: reranked_scores.get(cid, 0.0),
                        reverse=True,
                    )
                    final_ids_scores = [(cid, reranked_scores.get(cid, 0.0)) for cid in ordered_ids]
                    reranked_flag = True
                else:
                    fused_scores = dict(fused)
                    final_ids_scores = [(cid, fused_scores.get(cid, 0.0)) for cid, _ in candidates]
                    reranked_flag = False

            results: List[RetrievedEvidence] = []
            for chunk_id, score in final_ids_scores[:top_k]:
                meta = self._chunk_metadata[chunk_id]
                results.append(
                    RetrievedEvidence(
                        chunk_id=chunk_id,
                        document_id=meta["document_id"],
                        title=meta["title"],
                        source=meta["source"],
                        text=meta["text"],
                        score=float(score),
                    )
                )

            diagnostics = {
                "dense_candidates": len(dense_ranked_ids),
                "sparse_candidates": len(sparse_ranked_ids),
                "fused_candidates": len(fused),
                "reranked": reranked_flag,
            }

            logger.info(
                "retrieval_completed",
                extra={"event": "retrieval_completed", "query": query, "returned": len(results), **diagnostics},
            )
            return results, diagnostics
