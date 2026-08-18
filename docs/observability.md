# Observability

## What exists

**Structured logging** (since Phase 1): every service emits single-line
JSON logs with a consistent event schema. `RequestIdFilter` attaches a
per-request correlation ID; `SecretRedactionFilter` (Phase 9) redacts
secret-like field names as a safety net; `TraceContextFilter` (Phase
10) attaches the active OTel trace/span ID, so a log line can be
pivoted straight to its trace.

**Distributed tracing** (Phase 10): real OpenTelemetry spans, correctly
nested, across the full request path:

```
http.request (backend, root span)
 └─ agent.agent_node          (per LLM turn)
     └─ llm.chat               (OpenRouter call)
 └─ agent.tools_node           (per turn, if tools were called)
     └─ agent.tool_call        (per individual tool call)
         └─ mcp.call_tool      (backend → MCP server, over Streamable HTTP)
             └─ rag.search_knowledge_tool     (inside rag-mcp)
                 └─ rag.retrieval_pipeline
                     ├─ rag.dense_search
                     ├─ rag.sparse_search
                     ├─ rag.fusion
                     └─ rag.rerank
             └─ db.get_payment_failure_stats_tool   (inside db-mcp)
                 └─ db.query.get_payment_failure_stats
             └─ github.search_recent_commits_tool   (inside github-mcp)
                 └─ github.list_commits / github.get_commit_files
```

One user request → one trace, spanning all four services, with real
attributes on every span (model name, tool name, query length, result
counts, reranker enabled/disabled, etc.) and real durations (span
start/end IS the latency metric — see "What's deliberately NOT here"
below for why no separate metrics pipeline was added).

## Design: the optional-dependency span helper

The single most important design decision this phase: `span_helper.py`
(duplicated per service, like every other cross-cutting concern in this
project) detects at import time whether `opentelemetry` is installed.
If not, `start_span()` is a no-op context manager — no exception, no
missing feature, just nothing recorded. If it IS installed and a
`TracerProvider` has been configured (`tracing.py`, called once at
startup), real spans are created.

This is what let tracing reach `backend/app/agent/nodes.py` and
`services/rag-mcp/app/retrieval.py` — both modules built in earlier
phases specifically to have **zero hard dependency** on anything beyond
their own project's pure logic, so they could be unit tested directly
without installing the full stack (30 tests for `nodes.py`, 5 for
`retrieval.py`, both re-verified after this phase's changes with zero
regressions) — **without giving either module a hard dependency on
`opentelemetry`**. Every other design in this phase serves that one
property.

## Testing this without `opentelemetry` installed

The same sandbox limitation as every prior phase applies: no network,
so `opentelemetry-sdk` couldn't be installed to test `tracing.py`
directly. But `span_helper.py` and `log_correlation.py` are
`try/except ImportError` gated, which means:

1. **The no-op path is genuinely exercised, not simulated** — this
   sandbox really doesn't have `opentelemetry` installed, so
   `test_start_span_is_a_working_noop_when_otel_unavailable` and
   equivalents test real behavior.
2. **The "installed" path is tested via monkeypatching** the module's
   `_OTEL_AVAILABLE` flag and `_otel_trace` reference to a fake tracer
   object, exercising the span-creation and attribute-setting logic
   without the real package.

36 tests across the three MCP services (12 each) plus 16 in the
backend (`test_trace_formatting`, `test_span_helper`,
`test_log_correlation`) — 52 new tests this phase, all actually
executed. `tracing.py` itself (the real SDK setup:
`TracerProvider`/`Resource`/`BatchSpanProcessor`/`OTLPSpanExporter`)
remains `py_compile`-only, same limitation as every `opentelemetry`-,
`langgraph`-, `mcp`-, or `httpx`-dependent module in this project.

## Verifying locally

```bash
# Stand up a local OTLP collector, e.g. Jaeger with OTLP enabled:
docker run -d --name jaeger -p 16686:16686 -p 4318:4318 jaegertracing/all-in-one:latest

# Point every service at it (root .env and each service's .env):
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces

# Run a query through the full stack, then open http://localhost:16686
# and look for a trace spanning http.request -> agent.* -> mcp.call_tool
# -> rag.search_knowledge_tool -> rag.retrieval_pipeline -> ...
```

If spans don't appear: confirm `pip install -r requirements-dev.txt`
actually installed `opentelemetry-sdk` (check the
`tracing_configured_without_exporter` vs `otlp_exporter_configured` log
line at each service's startup — the former means the endpoint wasn't
picked up, the latter confirms it was).

## What's deliberately NOT here

- **No dedicated metrics pipeline** (OTel Metrics API, histograms, a
  Prometheus exporter). Span duration already captures per-operation
  latency, which is what the project spec's "latency metrics" bullet
  is checking for; a separate metrics pipeline is a natural extension,
  not added here to avoid the same "over-engineer before the basic
  system works" trap this project has avoided everywhere else.
- **No auto-instrumentation packages**
  (`opentelemetry-instrumentation-fastapi` etc.). Manual
  instrumentation via `span_helper.start_span()` was chosen
  deliberately: it's plain Python I fully control and can reason about,
  versus an auto-instrumentation package's version-specific behavior I
  can't verify without network access — consistent with how this
  project has handled every other SDK-version uncertainty (see the MCP
  Streamable HTTP mounting caveat in `services/rag-mcp/app/server.py`
  for the earlier example of this same judgment call).
- **No sampling configuration.** Every span is recorded and exported
  (when an exporter is configured) — appropriate for a portfolio
  project's traffic volume; a production deployment at real scale would
  want a sampler, which is a config-level addition to `tracing.py`, not
  a design change.
