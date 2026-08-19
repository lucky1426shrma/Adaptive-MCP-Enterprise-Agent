"""CLI: ingest markdown documents into the RAG pipeline's indexes.

Usage (from services/rag-mcp/):
    python -m scripts.ingest --docs-dir data/sample_docs

Produces:
    - A populated Qdrant collection (dense vectors + payload)
    - data/index/chunks.jsonl (chunk text + metadata; BM25's corpus source)

This is an offline/admin operation, NOT an MCP tool — the agent never
triggers ingestion; it only calls `search_knowledge` against an
already-ingested index. Re-run this whenever source documents change,
and re-run against a fresh `QDRANT_COLLECTION` name if the embedding
model changes (never mix vectors from different embedding models in one
collection).
"""

from __future__ import annotations

import argparse
import json
import logging
import uuid
from pathlib import Path
from typing import List

from qdrant_client.http import models as qmodels

from app.chunking import chunk_text
from app.config import get_settings
from app.embeddings import BGEEmbeddingProvider
from app.logging_config import configure_logging
from app.vector_store import QdrantVectorStore, point_id_for_chunk

logger = logging.getLogger(__name__)


def _document_id_from_path(path: Path) -> str:
    return path.stem


def _title_from_markdown(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def ingest(docs_dir: Path, chunks_index_path: Path) -> None:
    settings = get_settings()
    embedding_provider = BGEEmbeddingProvider(settings.embedding_model)
    vector_store = QdrantVectorStore(
        collection_name=settings.qdrant_collection,
        vector_size=embedding_provider.dimension,
        url=settings.qdrant_url,
        local_path=settings.qdrant_local_path,
    )

    doc_paths = sorted(docs_dir.glob("*.md"))
    if not doc_paths:
        logger.warning(
            "no_documents_found", extra={"event": "no_documents_found", "docs_dir": str(docs_dir)}
        )
        return

    all_chunk_records: List[dict] = []
    points: List[qmodels.PointStruct] = []

    for doc_path in doc_paths:
        text = doc_path.read_text(encoding="utf-8")
        document_id = _document_id_from_path(doc_path)
        title = _title_from_markdown(text, fallback=document_id)

        chunks = chunk_text(text, document_id=document_id)
        if not chunks:
            logger.warning(
                "document_produced_no_chunks",
                extra={"event": "document_produced_no_chunks", "document_id": document_id},
            )
            continue

        vectors = embedding_provider.embed_documents([c.text for c in chunks])

        for chunk, vector in zip(chunks, vectors):
            record = {
                "chunk_id": chunk.chunk_id,
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "title": title,
                "source": str(doc_path),
                "text": chunk.text,
            }
            all_chunk_records.append(record)
            points.append(
                qmodels.PointStruct(
                    id=point_id_for_chunk(chunk.chunk_id),
                    vector=vector,
                    payload=record,
                )
            )

        logger.info(
            "document_ingested",
            extra={"event": "document_ingested", "document_id": document_id, "chunk_count": len(chunks)},
        )

    vector_store.upsert_chunks(points)

    chunks_index_path.parent.mkdir(parents=True, exist_ok=True)
    with chunks_index_path.open("w", encoding="utf-8") as f:
        for record in all_chunk_records:
            f.write(json.dumps(record) + "\n")

    logger.info(
        "ingestion_complete",
        extra={
            "event": "ingestion_complete",
            "documents": len(doc_paths),
            "chunks": len(all_chunk_records),
            "collection": settings.qdrant_collection,
            "chunks_index_path": str(chunks_index_path),
        },
    )


def main() -> None:
    settings = get_settings()
    configure_logging(log_level=settings.log_level, log_format=settings.log_format)

    parser = argparse.ArgumentParser(description="Ingest documents into the RAG pipeline.")
    parser.add_argument("--docs-dir", type=Path, default=Path("data/sample_docs"))
    parser.add_argument("--chunks-index-path", type=Path, default=settings.chunks_index_path)
    args = parser.parse_args()

    ingest(args.docs_dir, args.chunks_index_path)


if __name__ == "__main__":
    main()
