import { getServerMeta } from "@/lib/serverMeta";

export function ServerBadge({ server }: { server: string | null }) {
  const meta = getServerMeta(server);

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-surface-raised px-2 py-0.5 font-mono text-xs text-text-secondary">
      <span className={`h-1.5 w-1.5 rounded-full ${meta.dotClass}`} aria-hidden="true" />
      {meta.label}
    </span>
  );
}
