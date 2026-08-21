"""The actual chat API.

Unlike `app/api/rag_tools.py` / `db_tools.py` / `github_tools.py` (which
call one specific MCP tool directly, for integration verification),
this endpoint hands the question to the LangGraph agent, which decides
which tools — if any, from which servers — the question actually needs.
This is the project's core idea in its final, user-facing form.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agent.service import get_agent_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)


class ToolCallRecord(BaseModel):
    tool: str
    server: Optional[str]
    status: str
    latency_ms: float


class EvidenceItemResponse(BaseModel):
    chunk_id: str
    document_id: str
    title: str
    source: str
    text: str
    score: float


class TokenUsageResponse(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatResponse(BaseModel):
    answer: str
    tool_calls: List[ToolCallRecord]
    # Phase 11: the accumulated RAG evidence store (Phase 8), surfaced
    # so the frontend can render real citations — document title,
    # source, and the actual retrieved snippet — rather than only
    # whatever citation-like text the LLM happened to write in prose.
    # Deduplicated, highest-scoring version of each chunk, sorted by
    # score descending (same ordering as internally).
    evidence: List[EvidenceItemResponse]
    # Phase 12: accumulated LLM token usage across the whole run, for
    # the evaluation harness's "token usage" metric.
    token_usage: TokenUsageResponse
    iterations: int
    error: Optional[str]
    latency_ms: float


@router.post("", response_model=ChatResponse, summary="Ask the agent a question")
async def chat(payload: ChatRequest) -> ChatResponse:
    agent_service = get_agent_service()
    if agent_service is None:
        raise HTTPException(
            status_code=503,
            detail="The agent is not configured (OPENROUTER_API_KEY / OPENROUTER_MODEL not set, "
            "or the configured model failed startup validation).",
        )

    result = await agent_service.run(payload.message)

    return ChatResponse(
        answer=result.answer,
        tool_calls=[ToolCallRecord(**tc) for tc in result.tool_calls],
        evidence=[EvidenceItemResponse(**item) for item in result.evidence],
        token_usage=TokenUsageResponse(
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
        ),
        iterations=result.iterations,
        error=result.error,
        latency_ms=result.latency_ms,
    )
