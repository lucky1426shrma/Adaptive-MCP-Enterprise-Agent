import type { EvidenceItem } from "@/lib/types";

/**
 * Renders the ACTUAL structured evidence the backend returns (Phase 8's
 * evidence store, surfaced over the API in Phase 11 — see
 * backend/app/agent/service.py and app/api/chat.py) rather than trying
 * to pattern-match citation-like text out of the LLM's free-form prose
 * answer. This is deliberately the more honest approach: every item
 * shown here is something the agent actually retrieved and can be
 * verified against, not a guess at what a bracketed token in the
 * answer text might refer to.
 */
export function EvidenceList({ evidence }: { evidence: EvidenceItem[] }) {
  if (evidence.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-xs font-medium uppercase tracking-wide text-text-tertiary">
        Evidence ({evidence.length})
      </h3>
      <ul className="flex flex-col gap-2">
        {evidence.map((item) => (
          <li key={item.chunk_id} className="rounded-lg border border-border bg-surface-raised p-3">
            <div className="mb-1 flex items-start justify-between gap-3">
              <span className="text-sm font-medium text-text-primary">{item.title}</span>
              <span className="shrink-0 font-mono text-xs text-text-tertiary">
                score {item.score.toFixed(2)}
              </span>
            </div>
            <p className="line-clamp-3 text-sm text-text-secondary">{item.text}</p>
            <p className="mt-1.5 truncate font-mono text-xs text-text-tertiary">
              {item.chunk_id} · {item.source}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
