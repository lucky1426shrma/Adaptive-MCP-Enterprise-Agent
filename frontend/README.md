# Frontend — Investigation Console

Next.js 14 (App Router) + TypeScript + Tailwind chat interface for the
Adaptive MCP Enterprise Agent. Shows the user's question, the agent's
tool-call timeline (which MCP servers it decided to use, in what
order, with status and latency), the final cited answer, and the
structured evidence backing it.

## Architecture

```
Browser
  │  same-origin fetch, no CORS needed
  ▼
Next.js Route Handler (app/api/chat/route.ts)   ← server-side only
  │  attaches BACKEND_API_KEY here if configured, never in the browser
  ▼
FastAPI backend  POST /chat
```

The browser never talks to the FastAPI backend directly, and never
holds `BACKEND_API_KEY` — see `app/api/chat/route.ts`'s docstring for
the full reasoning. This mirrors the same "credentials stay server-side"
principle used everywhere else in this project (MCP servers never
exposing tokens to the LLM, the backend never exposing MCP credentials
to the frontend) applied one hop further, to this frontend itself.

## Setup

```bash
cd frontend
npm install
cp .env.example .env.local
# edit .env.local: BACKEND_URL should point at your running backend
# (default http://localhost:8000 matches the backend's own default port)

npm run dev
```

Open http://localhost:3000. The backend (and at least `rag-mcp` for a
non-trivial answer) needs to be running — see the root README for the
full stack startup order.

## Honest limitations (stated plainly)

- **No conversation persistence.** The thread lives in React state in
  the browser tab; refresh and it's gone. Matches the backend's own
  no-memory-across-requests design (Phase 7) — there's no session to
  persist yet, on either side.
- **No streaming.** The backend's `/chat` endpoint returns a single
  complete response (a known, documented Phase 7 limitation), so the
  tool timeline appears all at once when the response arrives, not
  incrementally as the agent works. The "Investigating…" state is
  honest about this — it doesn't fake a live step-by-step reveal.
- **Evidence display depends on the backend actually returning it.**
  `evidence` was added to the `/chat` response specifically in this
  phase (see `backend/app/api/chat.py`) to surface Phase 8's evidence
  store — if you're running an older backend build without that field,
  `EvidenceList` will just render nothing (empty array), not crash.
- **Not build-verified in the environment this was built in** — no
  npm registry access (see the root README for why). JSON configs were
  validated for syntax; TypeScript/JSX correctness could not be checked
  with the real toolchain. Run `npm run build` locally as the first
  verification step; if there's a type error, it's most likely in a
  component's prop types, not the overall architecture.

## What's NOT built yet (intentionally, matching project phasing)

- Auth UI (the console assumes either an open backend or a
  pre-shared `BACKEND_API_KEY` baked into the deployment's env — no
  login screen; per-user auth was explicitly out of scope, see
  `docs/security.md`).
- A raw trace/span viewer (Phase 10 built real OpenTelemetry tracing,
  but that data isn't surfaced through the chat API — it's meant for
  an OTLP backend like Jaeger, not this console).
