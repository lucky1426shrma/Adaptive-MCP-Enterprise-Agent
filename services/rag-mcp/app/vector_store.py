"""Qdrant wrapper: owns the dense-vector side of hybrid retrieval.

Points are stored with a deterministic UUID derived from `chunk_id`
(Qdrant point IDs must be an unsigned int or a UUID — our human-readable
`chunk_id` strings like "march-incident::chunk-3" aren't valid point IDs
directly). The original `chunk_id` is kept in the payload and is what
the rest of the pipeline actually keys on; re-ingesting the same chunk
deterministically overwrites the same point instead of duplicating it.
"""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

logger = logging.getLogger(__name__)


def point_id_for_chunk(chunk_id: str) -> str:
    """Deterministic UUID5 derived from a chunk_id, for use as a Qdrant point ID."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


class QdrantVectorStore:
    """Thin wrapper around Qdrant for the RAG chunk collection."""

    def __init__(
        self,
        collection_name: str,
        vector_size: int,
        url: Optional[str] = None,
        local_path: Optional[str] = None,
    ) -> None:
        if url:
            self._client = QdrantClient(url=url)
            logger.info("qdrant_connected_remote", extra={"event": "qdrant_connected_remote", "url": url})
        elif local_path:
            self._client = QdrantClient(path=local_path)
            logger.info("qdrant_connected_local", extra={"event": "qdrant_connected_local", "path": local_path})
        else:
            self._client = QdrantClient(location=":memory:")
            logger.info("qdrant_connected_memory", extra={"event": "qdrant_connected_memory"})

        self.collection_name = collection_name
        self.vector_size = vector_size
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self.collection_name in existing:
            return
        logger.info(
            "creating_qdrant_collection",
            extra={
                "event": "creating_qdrant_collection",
                "collection": self.collection_name,
                "vector_size": self.vector_size,
            },
        )
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qmodels.VectorParams(size=self.vector_size, distance=qmodels.Distance.COSINE),
        )

    def upsert_chunks(self, points: List[qmodels.PointStruct]) -> None:
        if not points:
            return
        self._client.upsert(collection_name=self.collection_name, points=points)
        logger.info(
            "chunks_upserted",
            extra={"event": "chunks_upserted", "collection": self.collection_name, "count": len(points)},
        )

    def search(self, query_vector: List[float], top_k: int) -> List[qmodels.ScoredPoint]:
        return self._client.search(
            collection_name=self.collection_name,
            query_vector=query_vector,
            limit=top_k,
            with_payload=True,
        )

    def count(self) -> int:
        return self._client.count(collection_name=self.collection_name, exact=True).count
