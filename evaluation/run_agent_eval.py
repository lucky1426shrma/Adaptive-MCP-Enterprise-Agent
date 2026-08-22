"""Runs evaluation/datasets/agent_eval_cases.jsonl against the live
backend's POST /chat, and scores what CAN be automated: tool-selection
accuracy (did the agent use at least the expected MCP servers), the
"extra servers used" signal (a proxy for unnecessary tool calls),
citation validity (see metrics.citation_validity_rate), token usage,
latency, iteration count, and failure/error rate.

Cases with `requires_manual_setup` are RUN but flagged prominently in
the report rather than silently scored the same as normal cases —
those categories (MCP server down, invalid LLM credentials) need the
operator to actually break something first. This script has no access
to process/container management for an arbitrary deployment and cannot
safely do that itself; pretending otherwise would misrepresent what
was actually tested. Their results are reported separately, not folded
into the automated accuracy summary.

ANSWER CORRECTNESS AND "UNSUPPORTED CLAIM RATE" ARE NOT AUTOMATICALLY
SCORED. See evaluation/README.md for why — briefly, doing so honestly
would need an NLP entailment model or an LLM-as-judge, which adds cost
and a new unverified assumption (judge reliability) this project isn't
built to validate. `answer_preview` is included in every result
specifically so a human can read it and judge quality directly.
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

from metrics import citation_validity_rate

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("evaluation.run_agent_eval")


async def evaluate_case(client: httpx.AsyncClient, case: Dict[str, Any]) -> Dict[str, Any]:
    try:
        response = await client.post("/chat", json={"message": case["question"]})
    except httpx.HTTPError as exc:
        return {"case_id": case["case_id"], "category": case["category"], "error": f"transport_error: {exc}"}

    if response.status_code != 200:
        return {
            "case_id": case["case_id"],
            "category": case["category"],
            "error": f"http_{response.status_code}",
            "detail": response.text[:300],
        }

    data = response.json()
    actual_servers = sorted({tc["server"] for tc in data["tool_calls"] if tc.get("server")})
    expected_servers = sorted(case.get("expected_servers", []))
    tool_selection_correct = set(expected_servers).issubset(set(actual_servers))
    extra_servers_used = sorted(set(actual_servers) - set(expected_servers))

    evidence_chunk_ids = {e["chunk_id"] for e in data.get("evidence", [])}
    citation_score = citation_validity_rate(data["answer"], evidence_chunk_ids)

    return {
        "case_id": case["case_id"],
        "category": case["category"],
        "requires_manual_setup": case.get("requires_manual_setup"),
        "question": case["question"],
        "expected_servers": expected_servers,
        "actual_servers": actual_servers,
        "tool_selection_correct": tool_selection_correct,
        "extra_servers_used": extra_servers_used,
        "citation_validity_rate": citation_score,
        "agent_reported_error": data.get("error"),
        "iterations": data.get("iterations"),
        "token_usage": data.get("token_usage"),
        "latency_ms": data.get("latency_ms"),
        "answer_preview": data["answer"][:300],
    }


def _accuracy(results) -> float | None:
    results = list(results)
    if not results:
        return None
    return round(sum(1 for r in results if r["tool_selection_correct"]) / len(results), 4)


async def main_async(args: argparse.Namespace) -> None:
    dataset_path = Path(args.dataset)
    cases = [json.loads(line) for line in dataset_path.read_text().splitlines() if line.strip()]

    async with httpx.AsyncClient(base_url=args.backend_url, timeout=120.0) as client:
        results = []
        for case in cases:
            logger.info(f"running {case['case_id']} ({case['category']})")
            results.append(await evaluate_case(client, case))

    automated = [r for r in results if not r.get("requires_manual_setup") and "error" not in r]
    manual = [r for r in results if r.get("requires_manual_setup")]
    errored = [r for r in results if "error" in r and not r.get("requires_manual_setup")]

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "benchmark_version": "phase-12-v1",
        "dataset": str(dataset_path),
        "backend_url": args.backend_url,
        "case_count": len(cases),
        "automated_case_count": len(automated),
        "manual_setup_case_count": len(manual),
        "errored_case_count": len(errored),
        "tool_selection_accuracy_automated_cases": _accuracy(automated),
        "note": (
            "manual_setup_case_count cases (MCP-server-down / invalid-credential "
            "scenarios) require the operator to break something first — see each "
            "case's requires_manual_setup field in the dataset. They ran against "
            "whatever the current (possibly unmodified) environment actually was, "
            "and are reported separately below, not folded into "
            "tool_selection_accuracy_automated_cases."
        ),
    }

    report = {"summary": summary, "results": results}
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2))

    logger.info("Agent eval complete:\n" + json.dumps(summary, indent=2))
    logger.info(f"Full report written to {output_path}")
    if manual:
        logger.warning(
            f"{len(manual)} case(s) require manual setup (see requires_manual_setup in "
            "the dataset) — confirm you actually performed that setup before trusting "
            "their individual results in the report."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate agent behavior against the golden case set.")
    parser.add_argument("--dataset", default="datasets/agent_eval_cases.jsonl")
    parser.add_argument("--backend-url", default="http://localhost:8000")
    parser.add_argument("--output", default="reports/agent_eval_report.json")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
