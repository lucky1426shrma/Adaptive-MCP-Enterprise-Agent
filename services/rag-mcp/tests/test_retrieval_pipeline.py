"""Tests for RetrievalPipeline's orchestration logic.

These use lightweight fakes for the embedding provider, vector store,
sparse index, and reranker instead of real Qdrant / BM25 / sentence-
transformers instances. That's possible because `app/retrieval.py`
only depends on those types structurally (duck typing), not by import —
see the `TYPE_CHECKING` guard in that module. This lets us verify the
fusion -> pool -> rerank -> top-K wiring is correct without needing the
full ML/vector-store stack installed.

A separate, fuller integration test against real Qdrant (local mode)
and real BM25 belongs in a later phase once those packages are part of
the normal dev install; this file intentionally stays dependency-light.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from app.retrieval import RetrievalPipeline


class FakeEmbeddingProvider:
    dimension = 4

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [[0.0, 0.0, 0.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        return [0.1, 0.2, 0.3, 0.4]


class _FakeScoredPoint:
    def __init__(self, chunk_id: str) -> None:
        self.payload = {"chunk_id": chunk_id}


class FakeVectorStore:
    """Returns a fixed, ordered list of chunk_ids regardless of the query vector."""

    def __init__(self, ranked_chunk_ids: List[str]) -> None:
        self._ranked_chunk_ids = ranked_chunk_ids

    def search(self, query_vector: List[float], top_k: int) -> List[_FakeScoredPoint]:
        return [_FakeScoredPoint(cid) for cid in self._ranked_chunk_ids[:top_k]]


class FakeSparseIndex:
    def __init__(self, ranked_chunk_ids: List[str]) -> None:
        self._ranked_chunk_ids = ranked_chunk_ids

    def search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        return [(cid, 1.0) for cid in self._ranked_chunk_ids[:top_k]]


class FakeReranker:
    """Reverses whatever order it's given, so tests can distinguish
    'fused order' from 'reranked order'."""

    def rerank(self, query: str, candidates: List[Tuple[str, str]]) -> List[Tuple[str, float]]:
        n = len(candidates)
        return [(chunk_id, float(n - i)) for i, (chunk_id, _) in enumerate(reversed(candidates))]


def _metadata_for(chunk_ids: List[str]) -> Dict[str, dict]:
    return {
        cid: {
            "document_id": f"doc-{cid}",
            "title": f"Title for {cid}",
            "source": f"source/{cid}.md",
            "text": f"Text content for {cid}",
        }
        for cid in chunk_ids
    }


def test_pipeline_returns_top_k_results_with_citations() -> None:
    chunk_ids = ["c1", "c2", "c3", "c4", "c5"]
    pipeline = RetrievalPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore(chunk_ids),
        sparse_index=FakeSparseIndex(list(reversed(chunk_ids))),
        reranker=None,
        chunk_metadata=_metadata_for(chunk_ids),
        dense_k=5,
        sparse_k=5,
        rerank_pool_size=5,
    )

    results, diagnostics = pipeline.run("some query", top_k=3)

    assert len(results) == 3
    for r in results:
        assert r.document_id.startswith("doc-")
        assert r.title
        assert r.source
        assert r.text
    assert diagnostics["dense_candidates"] == 5
    assert diagnostics["sparse_candidates"] == 5
    assert diagnostics["reranked"] is False


def test_item_ranked_high_in_both_dense_and_sparse_wins_without_reranker() -> None:
    # "shared" is #1 in dense and #2 in sparse -> should fuse to the top.
    dense = ["shared", "dense_only_1", "dense_only_2"]
    sparse = ["sparse_only_1", "shared", "sparse_only_2"]
    all_ids = list(dict.fromkeys(dense + sparse))

    pipeline = RetrievalPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore(dense),
        sparse_index=FakeSparseIndex(sparse),
        reranker=None,
        chunk_metadata=_metadata_for(all_ids),
        dense_k=10,
        sparse_k=10,
        rerank_pool_size=10,
    )

    results, _ = pipeline.run("query", top_k=1)
    assert results[0].chunk_id == "shared"


def test_reranker_can_override_fusion_order() -> None:
    chunk_ids = ["a", "b", "c"]
    pipeline = RetrievalPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore(chunk_ids),
        sparse_index=FakeSparseIndex([]),
        reranker=FakeReranker(),  # reverses order
        chunk_metadata=_metadata_for(chunk_ids),
        dense_k=10,
        sparse_k=10,
        rerank_pool_size=10,
    )

    results, diagnostics = pipeline.run("query", top_k=3)
    assert diagnostics["reranked"] is True
    # Fusion order (dense only) would be a, b, c. The fake reranker
    # reverses candidate order, so we expect c, b, a.
    assert [r.chunk_id for r in results] == ["c", "b", "a"]


def test_missing_metadata_for_a_candidate_is_silently_excluded() -> None:
    # Simulates a chunk_id returned by search but not present in the
    # in-memory metadata map (e.g. stale index) — should be skipped, not raise.
    dense = ["known", "unknown_chunk"]
    pipeline = RetrievalPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore(dense),
        sparse_index=FakeSparseIndex([]),
        reranker=None,
        chunk_metadata=_metadata_for(["known"]),  # "unknown_chunk" deliberately absent
        dense_k=10,
        sparse_k=10,
        rerank_pool_size=10,
    )

    results, _ = pipeline.run("query", top_k=5)
    assert [r.chunk_id for r in results] == ["known"]


def test_empty_indexes_return_no_results_without_error() -> None:
    pipeline = RetrievalPipeline(
        embedding_provider=FakeEmbeddingProvider(),
        vector_store=FakeVectorStore([]),
        sparse_index=FakeSparseIndex([]),
        reranker=None,
        chunk_metadata={},
        dense_k=10,
        sparse_k=10,
        rerank_pool_size=10,
    )

    results, diagnostics = pipeline.run("anything", top_k=5)
    assert results == []
    assert diagnostics["dense_candidates"] == 0
    assert diagnostics["sparse_candidates"] == 0
