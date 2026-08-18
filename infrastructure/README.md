# Infrastructure — Docker Compose deployment

Brings up all seven services: `postgres`, `qdrant`, `db-mcp`,
`rag-mcp`, `github-mcp`, `backend`, `frontend`.

## Honest status of this file

This is the **least-verified part of the entire project**. Every prior
phase's code was at minimum `py_compile`-checked or, for pure logic,
actually executed and tested — this sandbox has no Docker daemon and
no network access to pull base images, so nothing here was built or
run. What was checked: `docker-compose.yml` parses as valid YAML (see
below). Run `docker compose config` as your first real test before
`docker compose up` — it validates syntax and variable substitution
without building or starting anything.

## Setup

```bash
cd infrastructure
cp .env.example .env
# edit .env: set every "change-me" value, and OPENROUTER_API_KEY /
# OPENROUTER_MODEL (must be an explicitly free model — see the root
# README's Phase 7 section)
```

## Startup sequence (order matters — read this before `docker compose up`)

This is intentionally **not** fully automated with `depends_on`
completion conditions — see the comment at the top of
`docker-compose.yml` for why. Four steps, in order:

```bash
# 1. Bring up the stateful backing services first.
docker compose up -d postgres qdrant

# 2. Run the one-off setup jobs ONCE — these apply the DB schema +
#    seed data, and ingest the RAG sample documents. Both exit when
#    done; that's expected, not a crash.
docker compose --profile setup run --rm db-mcp-setup
docker compose --profile setup run --rm rag-mcp-ingest

# 3. Bring up everything else.
docker compose up -d

# 4. Verify.
curl http://localhost:8001/health/ready   # rag-mcp: pipeline loaded?
curl http://localhost:8002/health/ready   # db-mcp: can reach Postgres?
curl http://localhost:8003/health/ready   # github-mcp: GitHub API reachable?
curl http://localhost:8000/health/ready   # backend: can reach all configured MCP servers?
```

Then open http://localhost:3000.

## Re-running setup

- `rag-mcp-ingest` is safe to re-run any time source documents change —
  it re-ingests everything into the same Qdrant collection.
- `db-mcp-setup` is safe to re-run — it re-applies the schema
  (idempotent `CREATE TABLE IF NOT EXISTS`) and re-seeds data
  (`TRUNCATE` then insert, per `services/db-mcp/db/setup_and_seed.py`).
  Re-run it periodically if you want the "today" failure spike (Phase
  5) to stay recent relative to the actual current date, since it's
  generated relative to when the script runs.

## What's containerized vs. not, and why

Per the project spec ("do not unnecessarily containerize things that
complicate development"): everything that's part of the running
system is containerized here. Evaluation scripts (`evaluation/`) are
NOT — they're meant to be run from a developer's machine against a
running stack (containerized or not), not as long-running services
themselves.

## Known limitations, stated plainly

- **No TLS termination.** All ports are published directly, in plain
  HTTP. A real deployment needs a reverse proxy (nginx, Caddy, a cloud
  load balancer) in front of at least `frontend` and `backend`, with
  the MCP servers' ports NOT publicly exposed at all — this compose
  file exposes them (8001-8003) for direct debugging convenience,
  which is appropriate for local/demo use, not production. Remove
  those `ports:` mappings and let only `backend` reach them over the
  Docker network for anything beyond local use.
- **`rag-mcp`'s image is large and slow to build** (torch +
  sentence-transformers), and downloads model weights from Hugging
  Face on first container start (not at build time) — the first
  `docker compose up` will take meaningfully longer than every
  subsequent one. See `services/rag-mcp/Dockerfile`'s comments.
- **No package-lock.json for the frontend** (this project's build
  environment had no npm registry access to generate one — see the
  root README). `frontend/Dockerfile` handles its absence gracefully,
  but for a fully reproducible build, run `npm install` once locally
  and commit the resulting lockfile.
- **No automated backup/restore** for the `postgres_data` /
  `qdrant_data` volumes — out of scope for this project's spec, which
  never called for a specific backup strategy; use your normal volume
  backup tooling for whatever you deploy this on.
- **Remote/HTTPS MCP endpoints**: the project spec explicitly says
  "never hard-code localhost URLs" and "use HTTPS remote MCP
  endpoints" for production. This compose file uses Docker's internal
  service-name DNS (`http://rag-mcp:8001/mcp` etc.) rather than
  localhost, which satisfies "no hard-coded localhost" for this
  specific deployment target — but it's still plain HTTP over the
  Docker network, not TLS. For a genuinely distributed deployment
  (services on different hosts, not one Compose network), replace
  these URLs with real HTTPS endpoints via the same environment
  variables — no code changes needed, only `.env` values, since every
  service already reads its peer URLs from configuration (see Phase
  4-6 in the root README).
