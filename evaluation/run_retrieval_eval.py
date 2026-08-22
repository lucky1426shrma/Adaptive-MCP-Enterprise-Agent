"""Computes retrieval quality metrics (recall@k, precision@k, MRR)
against evaluation/datasets/rag_eval_seed.jsonl by calling the
backend's /mcp/rag/search integration-proof endpoint (Phase 4) for
each query.

NEVER FABRICATES RESULTS: every number in the output report comes from
an actual HTTP round trip to a running rag-mcp (via the backend), made
when this script is run. If rag-mcp hasn't been ingested
(services/rag-mcp/scripts/ingest.py), every query will legitimately
score near zero — that is a correct, honest result reflecting an empty
index, not a bug in this script.

To evaluate reranking effectiveness specifically (a documented gap
from Phase 3 — see services/rag-mcp/README.md's "Known limitations"):
run this script twice against two rag-mcp instances differing only in
ENABLE_RERANKER (true vs false), and diff the two reports' summaries.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import httpx

from metrics import mean_reciprocal_rank, precision_at_k, recall_at_k

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("evaluation.run_retrieval_eval")


async def evaluate_query(client: httpx.AsyncClient, case: Dict[str, Any], top_k: int) -> Dict[str, Any]:
    relevant = set(case["relevant_document_ids"])
    try:
        response = await client.post("/mcp/rag/search", json={"query": case["query"], "top_k": top_k})
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        return {"query_id": case["query_id"], "query": case["query"], "error": str(exc)}

    retrieved_ids = [r["document_id"] for r in data.get("results", [])]

    return {
        "query_id": case["query_id"],
        "query": case["query"],
        "relevant_document_ids": sorted(relevant),
        "retrieved_document_ids": retrieved_ids,
        "recall_at_k": recall_at_k(retrieved_ids, relevant, top_k),
        "precision_at_k": precision_at_k(retrieved_ids, relevant, top_k),
        "mrr": mean_reciprocal_rank(retrieved_ids, relevant),
    }


def _mean(values) -> float | None:
    values = list(values)
    return round(sum(values) / len(values), 4) if values else None


async def main_async(args: argparse.Namespace) -> None:
    dataset_path = Path(args.dataset)
    cases = [json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip()]

    async with httpx.AsyncClient(base_url=args.backend_url, timeout=30.0) as client:
        results = [await evaluate_query(client, case, args.top_k) for case in cases]

    scored = [r for r in results if "error" not in r]
    errored = [r for r in results if "error" in r]

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": "phase-12-v1",
        "dataset": str(dataset_path),
        "backend_url": args.backend_url,
        "top_k": args.top_k,
        "case_count": len(cases),
        "scored_count": len(scored),
        "errored_count": len(errored),
        "mean_recall_at_k": _mean(r["recall_at_k"] for r in scored),
        "mean_precision_at_k": _mean(r["precision_at_k"] for r in scored),
        "mean_mrr": _mean(r["mrr"] for r in scored),
    }

    report = {"summary": summary, "results": results}

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    logger.info("Retrieval eval complete:\n" + json.dumps(summary, indent=2))
    logger.info(f"Full report written to {output_path}")
    if errored:
        logger.warning(f"{len(errored)} of {len(cases)} queries errored — see the report for detail.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieval quality against the seed dataset.")
    parser.add_argument("--dataset", default="datasets/rag_eval_seed.jsonl")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--output", default="reports/retrieval_eval_report.json")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
