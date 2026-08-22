# Evaluation

## Status: real harness, no fabricated numbers

Everything in this directory is a runnable evaluation tool. **No
benchmark numbers are reported anywhere in this project's
documentation** — every script here makes real HTTP calls to a running
backend and computes metrics from the actual response, when *you* run
it. This directory existed since Phase 3 as a seed dataset with no
harness; Phase 12 is what actually built the harness around it.

## What's here

```
evaluation/
├── metrics.py                    # pure, dependency-free scoring functions (unit tested, 21 tests)
├── datasets/
│   ├── rag_eval_seed.jsonl        # 11 labeled retrieval queries (Phase 3, extended Phase 12)
│   └── agent_eval_cases.jsonl     # 9 golden agent-behavior cases, one per required test category
├── baseline_rag.py                # traditional single-shot RAG: one search, one LLM call, no iteration
├── lib/openrouter_client.py       # minimal standalone OpenRouter client (baseline_rag.py's only LLM dependency)
├── run_retrieval_eval.py          # recall@k / precision@k / MRR against rag_eval_seed.jsonl
├── run_agent_eval.py              # tool-selection accuracy, citation validity, latency, tokens, per category
├── run_baseline_vs_agentic.py     # head-to-head: baseline_rag.py vs POST /chat, same questions, same model
└── reports/                       # output directory — gitignored, generated at runtime
```

## Setup

```bash
cd evaluation
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Requires a running backend (`backend/`) reachable at `--backend-url`
(default `http://localhost:8000`), which in turn requires rag-mcp
ingested (`services/rag-mcp/scripts/ingest.py`, including the new
`2026-05-log-injection-incident.md` document added this phase — see
below) and, for `run_agent_eval.py`/`run_baseline_vs_agentic.py`, a
configured `OPENROUTER_API_KEY`/`OPENROUTER_MODEL` on the backend.

## Running

```bash
# Retrieval quality only (no LLM calls, no API key needed)
python run_retrieval_eval.py

# Agent behavior across all 9 required test categories
python run_agent_eval.py

# Traditional RAG baseline vs the full agentic system
python run_baseline_vs_agentic.py --openrouter-api-key sk-... --openrouter-model some-model:free
```

Each writes a timestamped, versioned JSON report to `reports/` and
prints a summary. **Re-run any of these yourself to get real numbers**
— this README will never claim a specific score, because none were
generated in the environment this project was built in (no network
access to a live backend, Postgres, Qdrant, or OpenRouter — see the
root README for why).

## Metric definitions and what's automated vs. not

| Metric (from the project spec) | Automated here? | Where |
|---|---|---|
| Retrieval recall@k / precision@k | Yes | `run_retrieval_eval.py`, `metrics.py` |
| Mean reciprocal rank (MRR) | Yes | same |
| Tool-selection accuracy | Yes | `run_agent_eval.py` — expected servers must be a *subset* of actual (multi-tool cases may reasonably use extra tools) |
| Unnecessary tool calls | Partial | `extra_servers_used` field is reported per case as a signal, not a strict pass/fail — `expected_servers` is a minimum, not a maximum, so "extra" isn't automatically wrong |
| Citation/evidence correctness | Partial (**citation *validity*, not full correctness**) | `citation_validity_rate` — checks that any chunk-ID-shaped citation in the answer text actually exists in the evidence the agent retrieved. Returns `None` (not a score) when no chunk-ID citations are present, which is the common case since the system prompt asks for human-readable citations, not raw IDs |
| Latency | Yes | every script, per case and mean |
| Token usage | Yes | `run_agent_eval.py`/`run_baseline_vs_agentic.py`, surfaced via `/chat`'s `token_usage` field (added this phase — see root README) |
| Retrieval iterations | Yes | `iterations` field from `/chat` |
| Failure rate | Yes | `errored_count` in every summary |
| Reranking effectiveness | Yes, but requires two runs | Run `run_retrieval_eval.py` twice against two rag-mcp instances differing only in `ENABLE_RERANKER` (true/false), diff the summaries. Closes a gap explicitly flagged as unevaluated in `services/rag-mcp/README.md` since Phase 3 |
| **Answer correctness / task success** | **No** | Deliberately not automated — see below |
| **Unsupported claim rate** | **No** | Deliberately not automated — see below |

### Why answer correctness and unsupported-claim rate aren't automated

Both would need either an NLP entailment model or an LLM-as-judge to
do honestly. Both add real cost and complexity, and an LLM judge adds
a new unverified assumption this project has no way to validate
(judge reliability, judge bias, judge cost) without its own evaluation
— turtles all the way down. Rather than fake precision with a metric
that *looks* automated but rests on an unvalidated judge, every script
here includes `answer_preview` (the actual answer text, truncated) in
its report specifically so a human reads and judges these two
qualities directly. Building an LLM-judge pipeline is a legitimate
next step, not a gap that was overlooked — it's a scope line drawn on
purpose, consistent with this project's "don't over-engineer before
what exists works" principle applied throughout every prior phase.

## Test categories covered (`agent_eval_cases.jsonl`)

All 9 categories the spec requires, one case each: `rag_only`,
`db_only`, `github_only`, `multi_tool`, `insufficient_evidence`,
`adversarial_injection_document`, `invalid_tool_input`,
`mcp_server_failure`, `model_tool_calling_failure`. The last two need
you to actually break something first (stop a service, set a bad API
key) — each case's `requires_manual_setup` field says exactly what;
`run_agent_eval.py` runs them regardless but reports them separately
from the automated accuracy summary, since their correctness depends
on setup this script can't verify or perform itself.

## The adversarial test document

`services/rag-mcp/data/sample_docs/2026-05-log-injection-incident.md`
was added this phase specifically to give `agent-006` something real
to retrieve: a realistic incident-report document that legitimately
*contains* an embedded prompt-injection attempt ("Ignore previous
instructions...") as part of describing a real incident. Before this,
Phase 9's injection-detection scanner (`app/agent/injection_detection.py`)
had unit tests with fake data but nothing to actually retrieve
end-to-end. Re-ingest rag-mcp (`scripts/ingest.py`) to pick it up.

## Tests

```bash
pytest -v
```

`test_metrics.py` is fully dependency-free (stdlib only) and was
actually executed during development — 21 tests, all passing,
including the two easy-to-get-wrong edge cases: an empty relevant-
document set scoring *perfectly* (not zero) for recall/MRR, since
"correctly finding nothing" is the right behavior for a deliberately
unanswerable query; and `citation_validity_rate` returning `None`
rather than `0.0` when no chunk-ID-shaped citations exist at all,
since that's a different condition from "citations exist but are
wrong."
