"""Chunking for RAG ingestion.

Deliberately dependency-free (stdlib only) so it's trivially unit
testable without needing the embedding/vector-store stack installed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    chunk_index: int
    text: str


def _split_sentences(text: str) -> List[str]:
    text = text.strip()
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT_RE.split(text) if s.strip()]


def chunk_text(
    text: str,
    document_id: str,
    max_chars: int = 800,
    overlap_chars: int = 150,
) -> List[Chunk]:
    """Split `text` into overlapping chunks for embedding/indexing.

    Strategy: split into paragraphs, then sentences, then greedily pack
    sentences into chunks up to `max_chars`, carrying `overlap_chars` of
    trailing context into the next chunk so sentences near a chunk
    boundary aren't isolated from surrounding context.

    This is character-count based, not token-based — deliberately simple
    for a portfolio project. If token-exact sizing against a specific
    embedding model's limits becomes necessary, swap in a tokenizer-aware
    chunker behind this same function signature; nothing downstream
    depends on the sizing strategy.

    Raises:
        ValueError: if `max_chars` <= 0, or `overlap_chars` is negative
            or >= `max_chars`.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be >= 0 and < max_chars")

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    sentences: List[str] = []
    for paragraph in paragraphs:
        sentences.extend(_split_sentences(paragraph))

    if not sentences:
        return []

    chunks: List[Chunk] = []
    current = ""
    chunk_index = 0

    def _flush(content: str) -> None:
        nonlocal chunk_index
        chunks.append(
            Chunk(
                chunk_id=f"{document_id}::chunk-{chunk_index}",
                document_id=document_id,
                chunk_index=chunk_index,
                text=content,
            )
        )
        chunk_index += 1

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence

        if len(candidate) <= max_chars:
            current = candidate
            continue

        if current:
            _flush(current)
            overlap_tail = current[-overlap_chars:] if overlap_chars else ""
            current = f"{overlap_tail} {sentence}".strip()
        else:
            current = sentence

        # A single sentence (possibly with carried-over overlap) can still
        # exceed max_chars on its own — hard-split it rather than emit an
        # oversized chunk.
        while len(current) > max_chars:
            _flush(current[:max_chars])
            current = current[max_chars - overlap_chars:]

    if current:
        _flush(current)

    return chunks
