/**
 * Maps the exact status strings the backend's tools_node emits (see
 * backend/app/agent/nodes.py's `records.append({..., "status": ...})`
 * call sites) to plain-language labels and color. Falls back to a
 * readable transform of any unrecognized status rather than hiding it
 * — an unmapped status is still shown, just without special styling,
 * so a future backend status value never disappears from the UI.
 */

interface StatusMeta {
  label: string;
  textClass: string;
  bgClass: string;
}

const STATUS_META: Record<string, StatusMeta> = {
  success: { label: "success", textClass: "text-success", bgClass: "bg-success-dim" },
  error: { label: "error", textClass: "text-danger", bgClass: "bg-danger-dim" },
  server_unavailable: {
    label: "server unavailable",
    textClass: "text-danger",
    bgClass: "bg-danger-dim",
  },
  unknown_tool: { label: "unknown tool", textClass: "text-warning", bgClass: "bg-warning-dim" },
  rag_budget_exhausted: {
    label: "budget exhausted",
    textClass: "text-warning",
    bgClass: "bg-warning-dim",
  },
};

export function StatusPill({ status }: { status: string }) {
  const meta: StatusMeta = STATUS_META[status] ?? {
    label: status.replace(/_/g, " "),
    textClass: "text-text-secondary",
    bgClass: "bg-surface-raised",
  };

  return (
    <span className={`rounded-full px-2 py-0.5 font-mono text-xs ${meta.textClass} ${meta.bgClass}`}>
      {meta.label}
    </span>
  );
}
