import { NextRequest, NextResponse } from "next/server";

/**
 * Server-side proxy to the FastAPI backend's POST /chat.
 *
 * This exists specifically so `BACKEND_API_KEY` (the optional shared
 * key from backend Phase 9's `BackendAPIKeyMiddleware`) never reaches
 * the browser. If this route didn't exist and the browser called the
 * FastAPI backend directly, any `Authorization` header would have to
 * live in client-side JavaScript — visible in the network tab and the
 * shipped bundle to anyone who opens devtools. Route handlers run
 * server-side in Next.js, so `BACKEND_URL` and `BACKEND_API_KEY`
 * (deliberately NOT prefixed `NEXT_PUBLIC_`) stay server-only.
 *
 * This also means the browser never needs to know the backend's real
 * origin, and there's no CORS configuration needed for this path at
 * all (same-origin from the browser's perspective) — the FastAPI
 * backend's CORS settings remain relevant only for other, non-browser
 * or directly-configured clients.
 */

const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8000";
const BACKEND_API_KEY = process.env.BACKEND_API_KEY;

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid request body." }, { status: 400 });
  }

  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (BACKEND_API_KEY) {
    headers.Authorization = `Bearer ${BACKEND_API_KEY}`;
  }

  let backendResponse: Response;
  try {
    backendResponse = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      // The backend enforces its own overall agent timeout
      // (AGENT_TIMEOUT_SECONDS); no separate client-side timeout is
      // imposed here beyond the runtime's own defaults.
    });
  } catch {
    return NextResponse.json(
      { detail: "Could not reach the backend service." },
      { status: 502 }
    );
  }

  // Pass the backend's response through as-is — status code and JSON
  // body. The backend already sanitizes error detail (see
  // backend/app/api/mcp_helpers.py and main.py's global exception
  // handler); this proxy doesn't need to re-interpret it, just relay
  // it. lib/api.ts on the browser side maps status codes to
  // plain-language copy for display.
  const data = await backendResponse.json().catch(() => ({ detail: "Unexpected response from backend." }));
  return NextResponse.json(data, { status: backendResponse.status });
}
