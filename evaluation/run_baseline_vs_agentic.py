"""Compares the traditional single-shot RAG baseline (baseline_rag.py)
against the full agentic system (POST /chat) over the SAME question
set, under IDENTICAL conditions (same OpenRouter model, same backend
instance, same rag-mcp index) — the explicit "traditional RAG baseline
vs agentic MCP-RAG" comparison the project spec calls for.

Restricted to RAG-relevant questions from the seed dataset
(rag_eval_seed.jsonl) — comparing a RAG-only baseline against DB/GitHub
questions wouldn't be a fair or meaningful comparison; the baseline
structurally cannot answer those, by design (that's the whole point of
the comparison: showing what single-shot RAG misses).

Retrieval recall@k is computed for both systems (baseline: from its
direct search results; agentic: from the evidence array in its /chat
response). ANSWER CORRECTNESS ITSELF IS NOT AUTOMATICALLY SCORED — see
evaluation/README.md. `answer_preview` for both systems is included in
every comparison specifically so a human can read them side by side.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx

from baseline_rag import run_baseline
from metrics import recall_at_k

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("evaluation.run_baseline_vs_agentic")


async def run_agentic(client: httpx.AsyncClient, question: str) -> Dict[str, Any]:
    try:
        response = await client.post("/chat", json={"message": question})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        return {"error": str(exc)}


def _mean(values) -> float | None:
    values = list(values)
    return round(sum(values) / len(values), 4) if values else None


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

    comparisons = []
    async with httpx.AsyncClient(base_url=args.backend_url, timeout=120.0) as client:
        for case in cases:
            relevant = set(case["relevant_document_ids"])
            logger.info(f"comparing {case['query_id']}: {case['query']}")

            baseline_result = await run_baseline(
                case["query"], args.backend_url, api_key, model, top_k=args.top_k
            )
            agentic_result = await run_agentic(client, case["query"])
            agentic_ok = "error" not in agentic_result

            agentic_retrieved_ids = (
                [e["document_id"] for e in agentic_result.get("evidence", [])] if agentic_ok else []
            )

            comparisons.append(
                {
                    "query_id": case["query_id"],
                    "query": case["query"],
                    "relevant_document_ids": sorted(relevant),
                    "baseline": {
                        "retrieved_document_ids": baseline_result.retrieved_document_ids,
                        "recall_at_k": recall_at_k(baseline_result.retrieved_document_ids, relevant, args.top_k),
                        "latency_ms": baseline_result.latency_ms,
                        "answer_preview": baseline_result.answer[:300],
                        "error": baseline_result.error,
                    },
                    "agentic": {
                        "retrieved_document_ids": agentic_retrieved_ids,
                        "recall_at_k": (
                            recall_at_k(agentic_retrieved_ids, relevant, args.top_k) if agentic_ok else None
                        ),
                        "latency_ms": agentic_result.get("latency_ms"),
                        "tool_calls": agentic_result.get("tool_calls"),
                        "token_usage": agentic_result.get("token_usage"),
                        "answer_preview": agentic_result.get("answer", "")[:300],
                        "error": agentic_result.get("error"),
                    },
                }
            )

    valid = [c for c in comparisons if c["baseline"]["error"] is None and c["agentic"]["error"] is None]

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": "phase-12-v1",
        "model": model,
        "backend_url": args.backend_url,
        "case_count": len(cases),
        "valid_comparison_count": len(valid),
        "mean_baseline_recall_at_k": _mean(c["baseline"]["recall_at_k"] for c in valid),
        "mean_agentic_recall_at_k": _mean(
            c["agentic"]["recall_at_k"] for c in valid if c["agentic"]["recall_at_k"] is not None
        ),
        "mean_baseline_latency_ms": _mean(c["baseline"]["latency_ms"] for c in valid),
        "mean_agentic_latency_ms": _mean(
            c["agentic"]["latency_ms"] for c in valid if c["agentic"]["latency_ms"] is not None
        ),
        "note": (
            "Answer correctness is NOT auto-scored — review the answer_preview "
            "fields in `comparisons` manually. See evaluation/README.md for why."
        ),
    }

    report = {"summary": summary, "comparisons": comparisons}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    logger.info("Comparison complete:\n" + json.dumps(summary, indent=2))
    logger.info(f"Full report written to {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare the traditional single-shot RAG baseline vs the full agentic system."
    )
    parser.add_argument("--dataset", default="datasets/rag_eval_seed.jsonl")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--openrouter-api-key", default=None)
    parser.add_argument("--openrouter-model", default=None)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", default="reports/baseline_vs_agentic_report.json")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
