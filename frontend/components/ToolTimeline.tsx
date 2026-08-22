import type { ToolCallRecord } from "@/lib/types";
import { getServerMeta, toolDisplayName } from "@/lib/serverMeta";

import { ServerBadge } from "./ServerBadge";
import { StatusPill } from "./StatusPill";

/**
 * The console's signature element: a vertical, connected trace of
 * every tool call the agent made for this question, in order — a
 * direct visualization of the LangGraph tools_node loop (see
 * backend/app/agent/nodes.py) rather than a decorative timeline. An
 * EMPTY list is a legitimate, common outcome (the agent judged no
 * tool was needed) and is shown as an explicit statement, not a blank
 * space that could read as broken.
 */
export function ToolTimeline({ toolCalls }: { toolCalls: ToolCallRecord[] }) {
  if (toolCalls.length === 0) {
    return (
      <p className="text-sm text-text-secondary">
        No tools were needed — the agent answered directly from the question alone.
      </p>
    );
  }

  return (
    <ol className="flex flex-col gap-0">
      {toolCalls.map((call, index) => {
        const meta = getServerMeta(call.server);
        const isLast = index === toolCalls.length - 1;

        return (
          <li
            key={`${call.tool}-${index}`}
            className="flex animate-fade-in items-start gap-3"
            style={{ animationDelay: `${index * 70}ms` }}
          >
            <div className="flex flex-col items-center self-stretch">
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${meta.dotClass}`}
                aria-hidden="true"
              />
              {!isLast && <span className="w-px flex-1 bg-border" aria-hidden="true" />}
            </div>

            <div className={`flex flex-1 flex-wrap items-center gap-2 ${isLast ? "" : "pb-4"}`}>
              <ServerBadge server={call.server} />
              <span className="font-mono text-sm text-text-primary">
                {toolDisplayName(call.tool)}
              </span>
              <StatusPill status={call.status} />
              <span className="ml-auto font-mono text-xs text-text-tertiary">
                {call.latency_ms.toFixed(0)}ms
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
