# Security Model

This document consolidates security decisions made across every phase
into one audit. Most of the substance was built incrementally as each
service was built (auth boundaries in Phase 2, least-privilege DB role
in Phase 5, GitHub repo allow-listing in Phase 6, prompt-injection
instructions in Phase 7); Phase 9's job was closing genuine gaps — rate
limiting, defense-in-depth injection *detection* (not just
instruction), an optional backend-facing auth gate, and a secret-
redaction safety net — and writing this down in one place. This will
be folded into the top-level README's "Security model" section once
that's written (a later phase).

## Trust boundaries

```
Browser/client
     │  (no MCP credentials, no direct MCP access)
     ▼
FastAPI backend  ── optional BACKEND_API_KEY gate (Phase 9)
     │  each of the three connections below uses ITS OWN bearer token
     │  (RAG_MCP_AUTH_TOKEN / DB_MCP_AUTH_TOKEN / GITHUB_MCP_AUTH_TOKEN)
     │  — a compromised token for one MCP server does not grant access
     │  to another
     ▼
RAG MCP ──── Qdrant, BM25 index (read/write via ingestion only)
DB MCP ────── PostgreSQL, connected as `db_mcp_reader` (SELECT only)
GitHub MCP ── GitHub API, scoped to ALLOWED_REPOSITORIES (read only)
```

Every MCP server is an independent trust boundary: each validates its
own bearer token, none trusts network placement alone, and none holds
credentials for the others.

## Authentication

| Boundary | Mechanism | Status |
|---|---|---|
| Backend → RAG/DB/GitHub MCP | Per-server bearer token, checked by `BearerAuthMiddleware` | Phase 2 |
| Client → Backend | Optional `BACKEND_API_KEY` via `BackendAPIKeyMiddleware` | Phase 9 |
| Backend → OpenRouter | API key in `Authorization` header | Phase 7 |
| DB MCP → PostgreSQL | `db_mcp_reader` role credentials | Phase 5 |
| GitHub MCP → GitHub API | Least-privilege PAT | Phase 6 |

`BACKEND_API_KEY` is a single shared application-level key, not a
per-user authentication system. **This is a known, deliberate scope
limitation** — a real multi-user deployment needs proper user
authentication (OAuth/OIDC, session tokens) in front of this backend;
that's out of scope for this project's spec, which never called for a
user account system. Left unset, the backend is open — appropriate for
local development and single-operator demos, not for public exposure.

Every MCP server's `AUTH_TOKEN` fails closed outside `development`
environment if left at its insecure default (`validate_runtime()` in
each service's `config.py`, since Phase 2).

## Authorization (least privilege)

- **RAG MCP**: one tool, `search_knowledge` — no write path, no
  filesystem access beyond the pre-ingested index.
- **DB MCP**: connects as `db_mcp_reader`, a PostgreSQL role with
  `SELECT`-only grants (`services/db-mcp/db/setup_and_seed.py`); the
  running server never holds admin/superuser credentials. Query is
  parameterized and timeout-bounded; date range capped at 90 days.
- **GitHub MCP**: `ALLOWED_REPOSITORIES` allow-list enforced
  server-side (`app/repo_scope.py`), exact match only, **empty list
  denies everything** (fail closed, not fail open) — this is checked
  independent of what the caller/LLM requests, so a compromised or
  confused agent cannot expand its own access by asking nicely.
- **Backend → MCP servers**: the LLM never receives any MCP server's
  credentials; it only ever emits a tool NAME and arguments, which the
  backend resolves and executes (`app/agent/tool_catalog.py`,
  `app/agent/nodes.py`).

## Input validation

Every external input boundary is `pydantic`-validated before use:
tool schemas (`SearchKnowledgeInput`, `PaymentFailureStatsInput`,
`SearchRecentCommitsInput`), the backend's own request models
(`app/api/*.py`), and the chat endpoint's `ChatRequest` (message length
capped at 2000 chars). Nothing user- or LLM-supplied reaches a SQL
query, a GitHub API path, or a vector search without passing through a
typed schema first.

## Prompt injection

Two independent layers, deliberately not just one:

1. **Instructional** (`app/agent/prompts.py`, Phase 7): the system
   prompt explicitly tells the LLM that tool results are data, never
   instructions, and gives concrete examples of what an injection
   attempt looks like.
2. **Structural / detection** (`app/agent/injection_detection.py`,
   Phase 9): every tool result is scanned against a small set of
   known injection phrase patterns (`ignore previous instructions`,
   `you are now`, `reveal your system prompt`, etc.). A match prepends
   a loud `[SECURITY NOTICE: ...]` banner to that specific tool result
   before the LLM sees it, and logs the event
   (`tool_result_injection_pattern_detected`) for observability.

This is explicitly **flagging, not filtering** — retrieved documents
can legitimately discuss or quote injection-like text (e.g. security
training material), and the content still needs to reach the LLM as
evidence to reason about. The pattern list is a heuristic, not
exhaustive; it cannot replace instruction #1, only add a second,
independent signal.

## Rate limiting

`app/security/rate_limiter.py` + `rate_limit_middleware.py` (Phase 9):
an in-memory sliding-window limiter, applied per client IP (or the
first `X-Forwarded-For` entry, only if `TRUST_PROXY_HEADERS=true` and
only appropriate behind a reverse proxy that itself sets that header —
otherwise it's spoofable and must stay off). `/health` and
`/health/ready` are exempt so orchestrator probes aren't throttled.

**Known limitation, stated plainly**: this is single-process, in-memory
state. It does not coordinate across multiple backend replicas. A real
multi-instance deployment needs a shared store (Redis, etc.) — the
`RateLimiter` class is a small, swappable component specifically so
that upgrade doesn't require touching the middleware around it.

## Secret management

- No secret is ever hard-coded; every credential is environment-variable
  configured (see the root and per-service `.env.example` files).
- No `.env` file is committed (`.gitignore` since Phase 1).
- Bearer-token comparisons never log the token value, only the fact of
  a rejection (`BearerAuthMiddleware`, `BackendAPIKeyMiddleware`).
- `SecretRedactionFilter` (`app/security/log_redaction.py`, duplicated
  per-service like every other cross-cutting concern in this project)
  is a **defense-in-depth safety net**: it redacts the *value* of any
  structured log field whose *name* looks secret-like
  (`api_key`, `token`, `password`, `dsn`, `connection_string`, ...).
  It cannot catch a secret embedded in a free-text log message string
  — avoiding that pattern remains a code-review discipline, not
  something this filter replaces.
- `services/db-mcp/db/setup_and_seed.py`'s reader-role password
  provisioning is explicitly documented as local-dev-appropriate only
  (embeds the password into a DDL string with basic escaping) — a real
  deployment should provision that role via infrastructure/secrets
  tooling instead.

## CORS

Tightened in Phase 9 from wildcard methods/headers to exactly what the
frontend needs: `GET, POST, OPTIONS` and `Authorization, Content-Type`.
Origins remain configurable via `CORS_ALLOWED_ORIGINS` (comma-separated).

## Error sanitization

- Every MCP-calling route (`app/api/rag_tools.py`, `db_tools.py`,
  `github_tools.py`, `chat.py`) maps each `MCPClientError` subtype to a
  specific, generic HTTP status and message (`app/api/mcp_helpers.py`)
  — never the raw exception text, which could contain internal URLs.
- A global exception handler (`app/main.py`, Phase 9) catches anything
  NOT already handled by a route's own logic, logs the full exception
  server-side with the request's correlation ID, and returns a bare
  `{"detail": "Internal server error."}` — no stack trace, no internal
  detail, ever reaches the client for an unanticipated failure.
- Every DB/GitHub MCP server error path already returned sanitized
  messages before Phase 9 (Phases 5-6); this phase's addition is the
  backend-level safety net for bugs *outside* those already-handled
  paths.

## What's explicitly out of scope (by design, not oversight)

- **Per-user authentication/authorization** — the spec describes a
  single-operator or trusted-internal-team tool, not a multi-tenant
  product; `BACKEND_API_KEY` is the appropriate-scope answer here.
- **Encryption at rest** for Qdrant/PostgreSQL data — left to the
  deployment environment (a managed Postgres/Qdrant instance's own
  encryption, or disk-level encryption), not application code.
- **Automated secret rotation** — credentials are environment-variable
  configured so rotation is an infrastructure/ops concern, not
  something the application implements.
- **A learned/ML-based injection classifier** — the heuristic pattern
  list is intentionally simple; a real classifier would need training
  data and evaluation this project doesn't have (Phase 12 doesn't
  exist yet), and would add cost/latency to every tool call.

## Testing coverage

`app/security/rate_limiter.py`, `app/agent/injection_detection.py`, and
`app/security/log_redaction.py` are dependency-free and directly unit
tested (30 tests across `test_rate_limiter.py`,
`test_injection_detection.py`, `test_log_redaction.py`, all actually
executed during development, not just compiled). `test_agent_nodes.py`
covers the actual wiring — injection banners appearing in tool results
sent to the LLM, for both RAG and non-RAG tool sources.
`rate_limit_middleware.py` and `api_key_middleware.py` need
`starlette`/`httpx` installed to test; `py_compile`-verified only in
the environment this was built in, same limitation as every other
phase's `starlette`-dependent code.
