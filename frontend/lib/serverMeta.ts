/**
 * Single source of truth for how each MCP server is labeled and
 * colored across the UI (ServerBadge, ToolTimeline). Kept in one place
 * so the badge and the timeline dot can never drift out of sync with
 * each other.
 */

export interface ServerMeta {
  label: string;
  dotClass: string;
}

const SERVER_META: Record<string, ServerMeta> = {
  rag: { label: "RAG", dotClass: "bg-server-rag" },
  db: { label: "DB", dotClass: "bg-server-db" },
  github: { label: "GitHub", dotClass: "bg-server-github" },
};

export function getServerMeta(server: string | null): ServerMeta {
  if (server && server in SERVER_META) {
    return SERVER_META[server] as ServerMeta;
  }
  return { label: server ?? "unknown", dotClass: "bg-text-tertiary" };
}

/** Tool names arrive prefixed as "server__toolname" (see backend's
 * app/agent/tool_catalog.py) — this strips the prefix for display. */
export function toolDisplayName(prefixedName: string): string {
  const idx = prefixedName.indexOf("__");
  return idx === -1 ? prefixedName : prefixedName.slice(idx + 2);
}
