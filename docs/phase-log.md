# Adaptive MCP Enterprise Agent

A production-oriented agentic RAG system where an LLM-driven LangGraph agent
dynamically selects and invokes capabilities — document retrieval,
structured/live data, and source-code context — exposed through independent
MCP servers, instead of a single hardcoded retrieval pipeline.

> **Status:** Phases 1–12 complete (project foundation; MCP server
> skeletons over Streamable HTTP; RAG hybrid retrieval pipeline; backend
> MCP client layer wired to RAG MCP; real PostgreSQL-backed DB MCP; real
> GitHub-API-backed GitHub MCP; LangGraph agent with dynamic tool
> selection over OpenRouter; agentic RAG with evidence accumulation and
> a RAG-specific retrieval budget; security hardening; distributed
> tracing across all four services; a Next.js investigation console; a
> reproducible evaluation harness). This README will be expanded into
> the full project documentation (problem, architecture, agent
> workflow, RAG pipeline, MCP servers, security model, observability,
> evaluation, setup, deployment, limitations) as later phases land.

## Target architecture

```
User → Next.js frontend → FastAPI backend → LangGraph agent → OpenRouter (free LLM)
                                  │
                            MCP Client (Streamable HTTP)
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
           RAG MCP             DB MCP             GitHub MCP
        (Qdrant + BM25      (PostgreSQL,        (GitHub API,
         + reranker)         read-only)          read-only)
```

MCP is the capability/protocol boundary. RAG is one capability exposed
through MCP — not a synonym for MCP. The LLM never touches Qdrant,
PostgreSQL, or the GitHub API directly; it only selects tools. Execution
always flows `LLM → LangGraph → MCP Client → MCP Server → resource`.

## Repository layout

```
project/
├── frontend/          Next.js chat UI                         (later phase)
├── backend/            FastAPI + LangGraph + MCP client        (this phase: FastAPI skeleton)
├── services/
│   ├── rag-mcp/        RAG MCP server (Qdrant, BM25, reranker)  (later phase)
│   ├── db-mcp/         PostgreSQL MCP server                   (later phase)
│   └── github-mcp/     GitHub MCP server                       (later phase)
├── shared/              shared schemas/config, if genuinely needed
├── evaluation/          reproducible retrieval/agent evaluation scripts
├── infrastructure/      Docker / Docker Compose / deployment config
├── docs/                architecture notes, diagrams
├── .env.example
└── README.md
```

## Phase 1 — project foundation

The `backend/` service is a FastAPI skeleton with:

- centralized, environment-variable-based configuration (`app/config.py`)
- structured JSON logging with request-correlation IDs (`app/logging_config.py`, `app/middleware.py`)
- liveness/readiness health endpoints (`app/api/health.py`)
- unit tests for the above (`tests/`)

No MCP client, agent, LLM calls, database, or frontend yet.

## Phase 2 — MCP server skeletons

Three independently deployable services under `services/`, each a
Starlette app exposing **Streamable HTTP** at `/mcp`, bearer-token auth
on that mount only, and open `/health` + `/health/ready` routes:

- `services/rag-mcp/` — real hybrid retrieval (see Phase 3)
- `services/db-mcp/` — one schema-validated **stub** tool (`get_payment_failure_stats`); real PostgreSQL lands in Phase 5
- `services/github-mcp/` — one schema-validated **stub** tool (`search_recent_commits`); real GitHub API lands in Phase 6

The FastMCP-inside-Starlette mounting pattern used in every `server.py`
carries an explicit verification note — see each service's README.

## Phase 3 — RAG pipeline

`services/rag-mcp/` implements hybrid retrieval end-to-end:

```
Query → Dense (Qdrant, BGE embeddings) + Sparse (BM25) → Reciprocal Rank Fusion
      → Cross-encoder rerank → Top-K cited evidence
```

- `app/chunking.py` — dependency-free chunker
- `app/embeddings.py` — `EmbeddingProvider` → `BGEEmbeddingProvider` (BAAI/bge-small-en-v1.5, local)
- `app/vector_store.py` — Qdrant wrapper
- `app/sparse_index.py` — BM25 wrapper
- `app/fusion.py` — reciprocal rank fusion (dependency-free)
- `app/reranker.py` — `Reranker` → `CrossEncoderReranker` (local cross-encoder)
- `app/retrieval.py` — orchestrates all of the above
- `scripts/ingest.py` — offline ingestion CLI
- `data/sample_docs/` — 4 sample enterprise documents (payment incident, auth architecture, retry policy, infra runbook)
- `evaluation/datasets/rag_eval_seed.jsonl` — seed labeled queries for the Phase 12 eval harness (not yet run)

See `.env.example` for the full configuration surface planned for all
later phases (commented out; not yet read by the app).

## Phase 4 — backend MCP client (wired to RAG MCP)

`backend/app/mcp/` is the backend's MCP client layer:

- `client.py` — `MCPServerClient`: connects over Streamable HTTP,
  discovers tools, invokes them, parses results. A fresh session is
  opened per call rather than held long-lived (see docstring for the
  trade-off).
- `parsing.py` — dependency-free result-content parsing (JSON-in-
  text-block extraction), unit tested directly.
- `exceptions.py` — `MCPConnectionError` / `MCPTimeoutError` /
  `MCPToolExecutionError` / `MCPProtocolError`, each mapped to a
  distinct, sanitized HTTP status by `app/api/mcp_helpers.py`.
- `registry.py` — builds one client per configured MCP server
  (`RAG_MCP_URL`, `DB_MCP_URL`) at startup.

`app/api/rag_tools.py` (`GET /mcp/rag/tools`, `POST /mcp/rag/search`)
and `app/api/db_tools.py` (`POST /mcp/db/payment-failure-stats`) are
**Phase 4/5 integration-proof endpoints** — they exist to verify the
MCP client layer end-to-end over real HTTP before the LangGraph agent
exists (Phase 7). They are not the final chat API.

`/health/ready` now checks connectivity to every configured MCP server.

## Phase 5 — Database MCP (real PostgreSQL)

`services/db-mcp/` now runs a real, read-only, parameterized query
against PostgreSQL instead of the Phase 2 stub:

- `db/schema.sql` — the `payments` table.
- `db/data_generation.py` — dependency-free synthetic data generation
  (unit tested), with an elevated failure rate during the March 2026
  incident window and a second spike ending "now".
- `db/setup_and_seed.py` — admin/bootstrap script: applies the schema,
  provisions a **SELECT-only** `db_mcp_reader` role, seeds data.
- `app/database.py` — pooled, parameterized, timeout-bounded query.

The running server only ever holds the read-only role's credentials —
never admin/superuser access — consistent with the project's
least-privilege requirement.

## Phase 6 — GitHub MCP (real GitHub API)

`services/github-mcp/` now calls the real GitHub REST API instead of
the Phase 2 stub:

- `app/repo_scope.py` — repository allow-list enforcement (exact match,
  fail-closed on empty list), unit tested independent of any I/O.
- `app/commit_shaping.py` — raw GitHub commit JSON → `CommitSummary`,
  unit tested independent of `httpx`.
- `app/github_client.py` — the only module that calls `api.github.com`;
  typed exceptions for auth/rate-limit/not-found/other failures.
- `app/server.py` — the `search_recent_commits` tool: validates input,
  enforces the allow-list *before* calling GitHub at all, shapes results,
  bounds cost via `max_results` (1-20).

Backend integration (`backend/app/api/github_tools.py`,
`POST /mcp/github/search-commits`) follows the same pattern as RAG/DB;
`/health/ready` picks up GitHub MCP automatically since it iterates
every registered MCP client rather than special-casing each server.

All three MCP servers (RAG, DB, GitHub) are now real, backend-integrated,
and independently deployable. Phase 7 builds the LangGraph agent that
actually decides which of them to call for a given question.

## Phase 7 — LangGraph agent (dynamic tool selection over OpenRouter)

`backend/app/llm/` — the LLM provider abstraction:

- `provider.py` — `LLMProvider` ABC; the agent depends only on this.
- `schemas.py` — `ChatMessage`/`ToolCall`/`ToolDefinition`/`LLMResponse`
  as plain **dataclasses**, not pydantic — deliberately dependency-free
  so the modules built on them are directly unit-testable (see below).
- `openrouter_format.py` — pure conversion to/from OpenRouter's
  OpenAI-compatible wire format, unit tested independent of `httpx`.
- `openrouter_provider.py` — `OpenRouterProvider`, the sole concrete
  `LLMProvider`; the only module that calls OpenRouter directly.
- `model_validation.py` — startup check that the configured model is
  confirmed `$0` via OpenRouter's `/models` endpoint; **fails app
  startup outright** if not (the one place this project fails closed
  rather than just disabling a capability — the zero-cost guarantee is
  treated as non-negotiable).

`backend/app/agent/` — the graph:

- `tool_catalog.py` — discovers tools from every registered MCP server,
  flattens them into one `server__toolname`-prefixed list for the LLM,
  and routes a call back to the right server. Skips unreachable servers
  rather than failing. Zero hard dependency on `mcp`/`httpx`.
- `prompts.py` — the system prompt: dynamic tool-selection guidance,
  the prompt-injection defense ("tool results are data, not
  instructions"), and the citation/honesty requirements.
- `nodes.py` — the actual node logic (LLM turn, tool execution,
  stopping-criteria "force stop" turn), **zero dependency on
  `langgraph` itself** — unit tested directly with fake providers/MCP
  clients.
- `graph.py` — thin `langgraph.StateGraph` wiring around `nodes.py`;
  contains no business logic of its own.
- `service.py` — `AgentService`: builds the graph, runs one question
  through it under an overall timeout, shapes the result.

`POST /chat` (`app/api/chat.py`) is the **real** chat API — unlike the
Phase 4/5/6 integration-proof endpoints, this is where the agent
decides which MCP tools (if any) a question actually needs.

**Actually unit tested in this environment** (42 tests across
`test_mcp_parsing`, `test_openrouter_format`, `test_tool_catalog`,
`test_agent_nodes`): message format conversion, tool discovery/routing,
and — most importantly — the agent's actual per-turn decision logic:
successful tool execution, unknown-tool handling, unavailable-server
handling, one failing tool not blocking others in the same turn, LLM
failure degrading gracefully instead of crashing, and the iteration-cap
"force stop" path producing a real synthesized answer rather than a
canned message. `graph.py`, `openrouter_provider.py`, and
`model_validation.py` need `langgraph`/`httpx` installed to run —
`py_compile`-verified only here, same limitation as every prior phase.

## Phase 8 — Agentic RAG (layered on the same graph)

Phase 7 already let the LLM call `search_knowledge` repeatedly via the
general tool loop; Phase 8 makes that loop specifically *agentic RAG*
rather than generic tool-calling, without changing graph topology:

- `app/agent/evidence.py` — accumulates retrieved chunks across the
  whole run, deduplicated by `chunk_id` (highest score wins) via a
  custom LangGraph state reducer, `merge_evidence_items`. This is what
  the final answer's citations are grounded in — a structured summary
  injected fresh into context every LLM turn, not the LLM re-parsing
  raw tool-result JSON from message history.
- `app/agent/retrieval_assessment.py` — a heuristic sufficiency note
  (`is_empty`, `is_weak`, top score, distinct-document count) attached
  to every `search_knowledge` result the LLM sees, so query-rewriting
  decisions have a real signal instead of a raw score buried in JSON.
- `app/agent/rag_loop_guard.py` — a RAG-specific retrieval budget
  (`RAG_MAX_RETRIEVAL_ATTEMPTS`, independent of the general
  `LLM_MAX_TOOL_ITERATIONS` cap) and verbatim-repeat-query detection,
  both deliberately simple per the project spec's warning against
  over-engineering this loop.
- `app/agent/nodes.py` — `run_tools_node` now special-cases
  `rag__search_knowledge` calls (identified by resolved
  `(server, tool)`, not string-matching) to apply the budget, flag
  repeats, extract evidence, and attach the assessment; `run_agent_node`
  and `run_force_stop_node` now inject the accumulated evidence summary
  as an ephemeral per-call context message (never persisted into
  conversation history, so it doesn't bloat turn over turn).

**Actually unit tested** (35 new tests: `test_evidence`,
`test_retrieval_assessment`, `test_rag_loop_guard`, plus the rewritten
`test_agent_nodes` with new Phase-8-specific cases): evidence dedup
keeping the higher score, sufficiency assessment on empty/weak/strong
results, budget exhaustion actually blocking the MCP call (not just
warning), a single LLM turn requesting more RAG calls than the budget
allows being partially honored and partially blocked, repeat-query
detection being case/whitespace-insensitive, and the evidence summary
appearing in context without leaking into persisted message history.
**103 tests passing across the whole repo** as of this phase.

## Phase 9 — Security

Full written audit: [`docs/security.md`](docs/security.md). Summary of
what's NEW this phase (most security work — MCP auth boundaries,
least-privilege DB role, GitHub allow-listing, pydantic validation
everywhere, prompt-injection instructions — was already built
incrementally in earlier phases and is just consolidated in that doc):

- `backend/app/security/rate_limiter.py` — in-memory sliding-window
  limiter, single-process (documented multi-replica limitation), wired
  in as `RateLimitMiddleware` with `/health` exempted.
- `backend/app/agent/injection_detection.py` — a SECOND, structural
  layer of prompt-injection defense on top of Phase 7's instructional
  one: every tool result is scanned for known injection patterns; a
  match prepends a loud warning banner (flagging, not filtering — the
  data still reaches the LLM as evidence) and logs the event.
- `backend/app/security/api_key_middleware.py` — optional
  `BACKEND_API_KEY` gate on the backend's own public endpoints,
  explicitly scoped as a single shared key, not a per-user auth system
  (documented limitation, not a gap presented as solved).
- `backend/app/security/log_redaction.py` — a logging-filter safety
  net redacting any log field whose *name* looks secret-like, deployed
  to the backend and (duplicated, consistent with every service's
  independent-deployability pattern) all three MCP servers.
- CORS tightened from wildcard methods/headers to exactly what the
  frontend needs; a global exception handler added as a safety net for
  anything not already sanitized by a route's own error handling.

**Actually unit tested** (30 new tests: `test_rate_limiter`,
`test_injection_detection`, `test_log_redaction`, plus 3 new wiring
cases in `test_agent_nodes` covering both RAG and non-RAG injection
sources): sliding-window expiry, per-client independent budgets,
case-insensitive pattern matching, a legitimate document *quoting* an
injection phrase still getting flagged (flagging, not filtering, is
deliberate), and secret redaction correctly ignoring non-string values
under a matching key name rather than crashing on them.
**136 tests passing across the whole repo** as of this phase.
`rate_limit_middleware.py` and `api_key_middleware.py` need
`starlette`/`httpx` installed to execute — `py_compile`-verified only
here, consistent with every prior phase's limitation.

## Phase 10 — Observability

Full write-up: [`docs/observability.md`](docs/observability.md). Real
OpenTelemetry distributed tracing across all four services, one trace
per request:

```
http.request (backend) → agent.agent_node → llm.chat
                       → agent.tools_node → agent.tool_call → mcp.call_tool
                           → rag.search_knowledge_tool → rag.retrieval_pipeline
                               → rag.dense_search / rag.sparse_search / rag.fusion / rag.rerank
                           → db.get_payment_failure_stats_tool → db.query...
                           → github.search_recent_commits_tool → github.list_commits / get_commit_files
```

**Key design decision**: `app/observability/span_helper.py`'s
`start_span()` is a no-op when `opentelemetry` isn't installed
(`try/except ImportError` at module load). This is what let tracing
reach `app/agent/nodes.py` and `services/rag-mcp/app/retrieval.py` —
both built in earlier phases specifically to have zero hard dependency
on anything beyond their own pure logic, for direct unit testing —
**without giving either module a hard dependency on `opentelemetry`**.
Both were re-verified with zero regressions after instrumentation (30
and 5 tests respectively, still passing, still importable with nothing
but the standard library).

Not mandatory, per the spec: `OTEL_EXPORTER_OTLP_ENDPOINT` unset means
spans are still created (real nesting, real durations) but never
exported anywhere — no external observability dependency required to
run this project.

**52 new tests this phase** (`test_trace_formatting`, `test_span_helper`,
`test_log_correlation`, ×4 services where applicable — 12 in each MCP
service, 16 in the backend), all actually executed, including both the
genuinely-exercised no-op path (opentelemetry really isn't installed in
this sandbox) and a monkeypatch-simulated "installed" path that
verifies span creation and attribute-setting logic.
**188 tests passing across the whole repo** as of this phase.
`tracing.py` (the real SDK setup) remains `py_compile`-only, same
limitation as every `opentelemetry`/`langgraph`/`mcp`/`httpx`-dependent
module in this project.

## Phase 11 — Frontend (Next.js investigation console)

`frontend/` — Next.js 14 (App Router) + TypeScript + Tailwind. Design
grounded in what this actually is (an internal console for watching an
agent decide which tools it needs across three trust boundaries), not
a generic AI-chat template: a dark, telemetry-toned palette (this
system is literally OpenTelemetry-traced end to end — Phase 10), IBM
Plex Sans/Mono, and a signature **tool timeline** component that
directly visualizes the LangGraph `tools_node` loop — server-colored,
connected steps with status and latency, not a decorative flourish.

**A real gap found and closed while building this phase**: the
backend's `/chat` response had no way to show real citations — Phase
8's evidence store existed only in internal agent state, never
serialized over the API. Closed with a small, additive backend change
(`AgentRunResult.evidence`, `ChatResponse.evidence`) rather than having
the frontend fake citations by parsing the LLM's free-form prose.
Re-verified zero regressions (30/30 agent node tests still passing)
since the change only touches `service.py`/`chat.py`, not `nodes.py`.

**Security carried through one more hop**: the browser never talks to
the FastAPI backend directly. `app/api/chat/route.ts` is a server-side
Next.js Route Handler that holds `BACKEND_URL` and the optional
`BACKEND_API_KEY` (Phase 9's shared-key gate) — neither ever reaches
client-side JavaScript. Same "credentials stay server-side" principle
used everywhere else in this project (MCP servers never exposing
tokens to the LLM, the backend never exposing MCP credentials to the
frontend), applied one hop further.

**Honesty in the UI itself**: an empty tool timeline is rendered as an
explicit "no tools were needed" statement, not a blank space that could
read as broken — the agent legitimately answering without tools is a
valid, common outcome. The "Investigating…" state doesn't fake a live
step-by-step reveal, since the backend's `/chat` is single-response,
not streaming (a documented Phase 7 limitation) — the full timeline
appears together when the response arrives.

**Verification honesty**: this sandbox has no npm registry access
(confirmed — `npm install next` returns 403), so nothing here was
`npm run build`-verified. What I could check: every `package.json`
and `tsconfig.json` is valid JSON; every `@/...` import resolves to a
real file (verified by script, zero missing); every source file has
balanced brackets/braces/parens (a coarse but real smoke test). Full
TypeScript type-checking needs to happen on your machine — see
`frontend/README.md` for setup and this phase's other stated
limitations (no conversation persistence, no streaming).

## Phase 12 — Evaluation

Full write-up: [`evaluation/README.md`](evaluation/README.md). A real,
runnable evaluation harness — **no benchmark numbers are reported
anywhere in this project**, because this sandbox has no network access
to a live backend/Postgres/Qdrant/OpenRouter to actually generate any.
Every script computes real metrics from real HTTP calls, when you run
it yourself:

- `run_retrieval_eval.py` — recall@k, precision@k, MRR against 11
  labeled queries (`datasets/rag_eval_seed.jsonl`, extended this phase).
- `run_agent_eval.py` — tool-selection accuracy, citation validity,
  latency, and token usage across **all 9 required test categories**
  (`datasets/agent_eval_cases.jsonl`): RAG-only, DB-only, GitHub-only,
  multi-tool, insufficient-evidence, adversarial-injection-document,
  invalid-tool-input, MCP-server-failure, model/tool-calling-failure.
- `baseline_rag.py` + `run_baseline_vs_agentic.py` — the explicit
  "traditional single-shot RAG vs agentic MCP-RAG" comparison the spec
  calls for, run under identical conditions (same model, same
  questions, same backend instance).

**Two more real gaps found and closed while building this phase, not
glossed over:**

1. **`token_usage` was computed internally (`LLMResponse.usage`) but
   never surfaced past the LLM provider layer** — closed the same way
   as Phase 11's evidence gap: additive fields threaded through
   `AgentState` (`prompt_tokens`/`completion_tokens`/`total_tokens`,
   simple sum reducers) → `AgentRunResult` → `ChatResponse.token_usage`.
   Re-verified zero regressions (33/33 `test_agent_nodes` tests
   passing, 3 new ones added specifically for token accumulation).
2. **Phase 9's injection-detection scanner had unit tests with fake
   data but nothing real to retrieve end-to-end.** Added
   `services/rag-mcp/data/sample_docs/2026-05-log-injection-incident.md`
   — a realistic incident report that legitimately contains an
   embedded injection attempt as part of describing a real incident —
   giving the `adversarial_injection_document` eval category something
   genuine to test against, closing the loop between Phase 9's unit
   tests and actual end-to-end behavior.

**Where the line was deliberately drawn**: answer correctness and
"unsupported claim rate" are **not** automated — both would need an
NLP entailment model or an LLM-as-judge, adding cost and a new
unvalidated assumption (judge reliability) this project has no way to
verify. Every report includes `answer_preview` so a human judges these
two qualities directly, rather than faking precision with an
unvalidated automated score. This is a scope line drawn on purpose,
consistent with "don't over-engineer before what exists works" applied
throughout every prior phase — not an oversight.

**21 new dependency-free tests** (`evaluation/tests/test_metrics.py`),
actually executed, including the two easy-to-get-wrong edge cases: an
empty relevant-document set scoring *perfectly* (not zero) for
recall/MRR — "correctly finding nothing" is right for a deliberately
unanswerable query — and `citation_validity_rate` returning `None`
rather than `0.0` when no chunk-ID-shaped citations exist at all, since
that's a different condition from "citations exist but are wrong."
**212 tests passing across the whole repo** as of this phase.

## Running the backend locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

cp ../.env.example .env          # optional — defaults work without it

uvicorn app.main:app --reload --port 8000
```

Then:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/health/ready
```

## Running tests

```bash
cd backend
pytest -v
```
