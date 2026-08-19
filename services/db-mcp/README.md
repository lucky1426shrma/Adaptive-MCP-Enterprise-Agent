# DB MCP

Exposes one tool, `get_payment_failure_stats`, over Streamable HTTP at
`/mcp`, backed by a real, read-only, parameterized PostgreSQL query
(Phase 5 — replaced the Phase 2 stub).

## Security model

This server connects to Postgres as `db_mcp_reader` — a role with
**SELECT-only** privileges, created by `db/setup_and_seed.py`. It never
holds admin/superuser credentials at runtime. The tool query is fully
parameterized (`$1`/`$2`/`$3`, never string-interpolated input) and
timeout-bounded (`QUERY_TIMEOUT_SECONDS`). Input validation (ISO dates,
end >= start, max 90-day range) happens before the query ever runs (see
`app/schemas.py`).

## Setup

Requires a running PostgreSQL instance. Locally, the simplest option:

```bash
docker run -d --name adaptive-mcp-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=adaptive_mcp \
  -p 5432:5432 postgres:16
```

Then:

```bash
cd services/db-mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python -m db.setup_and_seed \
  --admin-database-url postgresql://postgres:postgres@localhost:5432/adaptive_mcp \
  --reader-password some-local-dev-password
```

This applies `db/schema.sql`, creates/updates the `db_mcp_reader` role,
and seeds ~75 days of synthetic payment data — including an elevated
`gateway_error` rate during the March 2026 incident window (matching
`services/rag-mcp/data/sample_docs/2026-03-payment-gateway-incident.md`)
and a second, smaller spike in the last 2 hours before the script runs
(simulating an ongoing "today" issue, for the project's canonical demo
query).

```bash
cp .env.example .env
# Edit .env: set DATABASE_URL to use db_mcp_reader and the password you
# just chose, e.g.:
# DATABASE_URL=postgresql://db_mcp_reader:some-local-dev-password@localhost:5432/adaptive_mcp

python app/server.py   # or: uvicorn app.server:app --port 8002
```

```bash
curl http://localhost:8002/health
curl http://localhost:8002/health/ready   # checks real DB connectivity
```

## Tests

```bash
pytest -v
```

`test_data_generation.py` is dependency-light (pure Python + stdlib
`random`/`datetime`) and was actually executed during development,
including statistical checks that the incident/spike windows really do
produce elevated failure rates — not just syntax-checked. `test_schemas.py`
needs `pydantic` installed to run.

## Known limitations (Phase 5)

- Single table, single tool — no schema-inspection tool, no write paths.
- `setup_and_seed.py`'s reader-role provisioning embeds the password
  into a DDL string with basic quote-escaping; fine for local dev, not
  how you'd provision credentials in a real deployment (use your
  infra/secrets tooling there instead).
- No connection retry/backoff on startup — if Postgres isn't reachable
  when `database.connect()` runs, startup fails outright.
