"""Input/output schemas for the RAG MCP tool surface.

`SearchKnowledgeInput` is where user/agent-supplied arguments are
validated before touching the retrieval pipeline (never pass raw
LLM-generated input straight to a sensitive system without validation).
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class SearchKnowledgeInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Natural language search query.",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of evidence chunks to return (1-20).",
    )


class EvidenceChunk(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    source: str
    text: str
    score: float
    rank: int


class SearchKnowledgeResult(BaseModel):
    query: str
    results: List[EvidenceChunk]
    dense_candidates: int
    sparse_candidates: int
    fused_candidates: int
    reranked: bool
