"""Traditional single-shot RAG baseline: ONE retrieval call, stuff the
top-k results into a fixed prompt, ONE LLM call. No tool selection, no
iteration, no DB/GitHub — the explicit "retrieve -> stuff context ->
generate" pattern the project spec calls "traditional RAG," as the
comparison point against the full agentic system.

Retrieval goes through the backend's `/mcp/rag/search` integration-
proof endpoint (Phase 4) rather than talking to rag-mcp directly, so
this baseline exercises the exact same retrieval pipeline the agentic
system uses — the only difference under test is single-shot vs.
agentic tool use, not two different retrieval implementations.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import httpx

from lib.openrouter_client import simple_chat_completion

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("evaluation.baseline_rag")

SYSTEM_PROMPT = (
    "You answer questions using ONLY the provided context. If the context does not "
    "contain enough information to answer, say so explicitly rather than guessing. "
    "Cite the titles of the documents you used."
)


@dataclass
class BaselineResult:
    question: str
    answer: str = ""
    retrieved_document_ids: List[str] = field(default_factory=list)
    latency_ms: float = 0.0
    error: Optional[str] = None


async def run_baseline(
    question: str,
    backend_url: str,
    openrouter_api_key: str,
    openrouter_model: str,
    top_k: int = 5,
) -> BaselineResult:
    start = time.perf_counter()

    try:
        async with httpx.AsyncClient(base_url=backend_url, timeout=30.0) as client:
            response = await client.post("/mcp/rag/search", json={"query": question, "top_k": top_k})
            response.raise_for_status()
            search_result = response.json()
    except httpx.HTTPError as exc:
        return BaselineResult(
            question=question,
            error=f"retrieval_failed: {exc}",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    results = search_result.get("results", [])
    retrieved_document_ids = [r["document_id"] for r in results]

    context = (
        "\n\n".join(f'[{r["title"]}]\n{r["text"]}' for r in results) if results else "(no evidence retrieved)"
    )
    user_message = f"Context:\n{context}\n\nQuestion: {question}"

    try:
        answer = await simple_chat_completion(openrouter_api_key, openrouter_model, SYSTEM_PROMPT, user_message)
    except httpx.HTTPError as exc:
        return BaselineResult(
            question=question,
            retrieved_document_ids=retrieved_document_ids,
            error=f"llm_failed: {exc}",
            latency_ms=round((time.perf_counter() - start) * 1000, 2),
        )

    return BaselineResult(
        question=question,
        answer=answer,
        retrieved_document_ids=retrieved_document_ids,
        latency_ms=round((time.perf_counter() - start) * 1000, 2),
    )


async def main_async(args: argparse.Namespace) -> None:
    api_key = args.openrouter_api_key or os.environ.get("OPENROUTER_API_KEY")
    model = args.openrouter_model or os.environ.get("OPENROUTER_MODEL")
    if not api_key or not model:
        raise SystemExit(
            "Provide --openrouter-api-key/--openrouter-model or set "
            "OPENROUTER_API_KEY/OPENROUTER_MODEL."
        )

    dataset_path = Path(args.dataset)
    cases = [json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip()]

    results = []
    for case in cases:
        logger.info(f"running baseline for {case['query_id']}: {case['query']}")
        result = await run_baseline(case["query"], args.backend_url, api_key, model, top_k=args.top_k)
        results.append({"query_id": case["query_id"], **result.__dict__})

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps({"model": model, "results": results}, indent=2))
    logger.info(f"wrote {len(results)} baseline results to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the traditional single-shot RAG baseline over a dataset."
    )
    parser.add_argument("--dataset", default="datasets/rag_eval_seed.jsonl")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--openrouter-api-key", default=None)
    parser.add_argument("--openrouter-model", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", default="reports/baseline_results.json")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
