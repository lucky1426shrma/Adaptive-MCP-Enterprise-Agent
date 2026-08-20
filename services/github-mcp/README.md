# GitHub MCP

Exposes one tool, `search_recent_commits`, over Streamable HTTP at
`/mcp`, backed by the real GitHub REST API (Phase 6 — replaced the
Phase 2 stub).

## Security model

- **Repository allow-listing is enforced server-side** (`app/repo_scope.py`),
  independent of what the caller requests. `ALLOWED_REPOSITORIES` is a
  comma-separated exact-match list — no wildcards. An empty list denies
  every request (fail closed).
- **Least-privilege token**: `GITHUB_TOKEN` should be a read-only PAT
  (classic PAT with only the `repo` read scope, or a fine-grained PAT
  scoped to exactly the repositories in `ALLOWED_REPOSITORIES` with
  `Contents: Read-only`). This server is the only thing that ever holds
  it — never the backend, never the LLM.
- Every response is bounded: `max_results` (1-20) caps how many commits
  come back, and each tool call makes at most `1 + max_results` GitHub
  API requests (one list call, one file-detail call per commit).

## Setup

1. Create a GitHub PAT with read-only access to the repository/repos
   you want queryable.
2. `cp .env.example .env` and fill in `GITHUB_TOKEN` and
   `ALLOWED_REPOSITORIES`.

```bash
cd services/github-mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python app/server.py   # or: uvicorn app.server:app --port 8003
```

```bash
curl http://localhost:8003/health
curl http://localhost:8003/health/ready   # checks real GitHub API connectivity/auth
```

## Tests

```bash
pytest -v
```

`test_repo_scope.py` and `test_commit_shaping.py` are dependency-light
(pure Python, no `httpx` needed) and were actually executed during
development, not just syntax-checked — including the fail-closed
empty-allow-list case and the no-wildcard-matching case, since those are
the actual security properties this server relies on.

## Known limitations (Phase 6)

- Only default-branch commit history via `since`/`path` — no PR/issue
  search yet (deferred; the project spec lists these as potential
  future read tools, not required now).
- N+1 request pattern (one extra request per returned commit to fetch
  changed files) — bounded by `max_results`, but not batched.
- No caching — repeated identical queries re-hit the GitHub API and
  count against its rate limit.
