import type { Turn } from "@/lib/types";

import { AnswerText } from "./AnswerText";
import { EvidenceList } from "./EvidenceList";
import { ToolTimeline } from "./ToolTimeline";

export function InvestigationTurn({ turn }: { turn: Turn }) {
  return (
    <div className="flex flex-col gap-3">
      <div className="max-w-[85%] animate-fade-in self-end rounded-2xl rounded-br-sm border border-border bg-surface-raised px-4 py-2.5">
        <p className="text-sm text-text-primary">{turn.question}</p>
      </div>

      {turn.status === "pending" && (
        <div className="flex items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3">
          <span className="flex gap-1" aria-hidden="true">
            <span
              className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-accent"
              style={{ animationDelay: "0ms" }}
            />
            <span
              className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-accent"
              style={{ animationDelay: "160ms" }}
            />
            <span
              className="h-1.5 w-1.5 animate-pulse-dot rounded-full bg-accent"
              style={{ animationDelay: "320ms" }}
            />
          </span>
          <span className="text-sm text-text-secondary">Investigating…</span>
        </div>
      )}

      {turn.status === "failed" && (
        <div className="rounded-xl border border-danger/30 bg-danger-dim px-4 py-3">
          <p className="text-sm text-danger">{turn.failureMessage}</p>
        </div>
      )}

      {turn.status === "done" && turn.response && (
        <div className="flex animate-fade-in flex-col gap-4 rounded-xl border border-border bg-surface p-4">
          <div>
            <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-text-tertiary">
              Tool timeline
            </h3>
            <ToolTimeline toolCalls={turn.response.tool_calls} />
          </div>

          <div className="h-px bg-border" aria-hidden="true" />

          <AnswerText text={turn.response.answer} />

          {turn.response.error && (
            <p className="rounded-lg bg-warning-dim px-3 py-2 text-xs text-warning">
              The agent flagged an issue while investigating (
              {turn.response.error.replace(/_/g, " ")}) — the answer above may be based on
              incomplete evidence.
            </p>
          )}

          <EvidenceList evidence={turn.response.evidence} />

          <div className="flex items-center gap-3 font-mono text-xs text-text-tertiary">
            <span>
              {turn.response.iterations} step{turn.response.iterations === 1 ? "" : "s"}
            </span>
            <span aria-hidden="true">·</span>
            <span>{(turn.response.latency_ms / 1000).toFixed(1)}s total</span>
          </div>
        </div>
      )}
    </div>
  );
}
