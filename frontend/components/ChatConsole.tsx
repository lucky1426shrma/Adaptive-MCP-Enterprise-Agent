"use client";

import { useState } from "react";

import { askAgent, ChatRequestError } from "@/lib/api";
import type { Turn } from "@/lib/types";

import { EmptyState } from "./EmptyState";
import { InvestigationTurn } from "./InvestigationTurn";
import { QuestionInput } from "./QuestionInput";

function makeTurnId(): string {
  return `turn-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Owns the whole conversation thread client-side, in memory, for the
 * current browser session only — there is no server-side conversation
 * persistence (matches the backend's own no-memory-across-requests
 * design from Phase 7; each /chat call is a fresh agent run). Refreshing
 * the page loses the thread; this is a known, documented limitation
 * (see frontend/README.md), not an oversight.
 *
 * Only one investigation runs at a time — the input is disabled while
 * any turn is pending, rather than allowing concurrent requests that
 * could arrive out of order.
 */
export function ChatConsole() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const isPending = turns.some((turn) => turn.status === "pending");

  async function handleSubmit(question: string) {
    const id = makeTurnId();
    setTurns((prev) => [
      ...prev,
      { id, question, status: "pending", response: null, failureMessage: null },
    ]);

    try {
      const response = await askAgent(question);
      setTurns((prev) =>
        prev.map((turn) => (turn.id === id ? { ...turn, status: "done", response } : turn))
      );
    } catch (error) {
      const message =
        error instanceof ChatRequestError
          ? error.message
          : "Something unexpected went wrong.";
      setTurns((prev) =>
        prev.map((turn) =>
          turn.id === id ? { ...turn, status: "failed", failureMessage: message } : turn
        )
      );
    }
  }

  return (
    <div className="mx-auto flex h-screen max-w-2xl flex-col px-4 py-6">
      <header className="mb-4 flex shrink-0 items-center gap-2">
        <span className="h-2 w-2 rounded-full bg-accent" aria-hidden="true" />
        <span className="font-mono text-sm text-text-secondary">
          adaptive-mcp-enterprise-agent
        </span>
      </header>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto pb-4">
        {turns.length === 0 ? (
          <EmptyState onSelectExample={handleSubmit} />
        ) : (
          turns.map((turn) => <InvestigationTurn key={turn.id} turn={turn} />)
        )}
      </div>

      <div className="sticky bottom-0 shrink-0 border-t border-border bg-bg pt-4">
        <QuestionInput onSubmit={handleSubmit} disabled={isPending} />
      </div>
    </div>
  );
}
