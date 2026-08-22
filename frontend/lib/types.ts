/**
 * Mirrors backend/app/api/chat.py's response models exactly. If that
 * contract changes, this is the one file to update — every component
 * imports types from here rather than inlining shapes, so a backend
 * contract change surfaces as TypeScript errors here, not silent
 * `undefined`s scattered through the UI.
 */

export interface ChatRequest {
  message: string;
}

export interface ToolCallRecord {
  tool: string;
  server: string | null;
  status: string;
  latency_ms: number;
}

export interface EvidenceItem {
  chunk_id: string;
  document_id: string;
  title: string;
  source: string;
  text: string;
  score: number;
}

export interface ChatResponse {
  answer: string;
  tool_calls: ToolCallRecord[];
  evidence: EvidenceItem[];
  iterations: number;
  error: string | null;
  latency_ms: number;
}

/**
 * One question/answer turn in the console's thread. `status` tracks
 * the turn's own lifecycle in the UI — separate from `response.error`,
 * which is the AGENT's own reported error (e.g. it hit the iteration
 * cap but still produced an answer). A turn can be `status: "done"`
 * while `response.error` is non-null; that's a real, valid state (the
 * agent degraded gracefully), not a UI bug — see InvestigationTurn.
 */
export type TurnStatus = "pending" | "done" | "failed";

export interface Turn {
  id: string;
  question: string;
  status: TurnStatus;
  response: ChatResponse | null;
  /** Only set when status is "failed" — a transport/HTTP-level
   * failure (network error, non-2xx response), NOT the same thing as
   * response.error (see above). Always plain language, never a raw
   * status code or stack trace. */
  failureMessage: string | null;
}
