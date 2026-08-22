"use client";

// The first example is this project's canonical demo query (see the
// root README) — deliberately shown first since it's the clearest
// illustration of why the agent exists: it needs DB + RAG + GitHub
// together, not any single source alone.
const EXAMPLE_QUESTIONS = [
  "Why did payment failures increase today, and is this related to the March incident?",
  "What does our authentication architecture document say about token rotation?",
  "What changed in the payment service in the last week?",
];

export function EmptyState({ onSelectExample }: { onSelectExample: (question: string) => void }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 px-4 py-12 text-center">
      <div className="flex flex-col gap-2">
        <p className="font-mono text-xs uppercase tracking-widest text-accent">
          Investigation console
        </p>
        <h1 className="text-xl font-medium text-text-primary">
          Ask a question. Watch what the agent decides to check.
        </h1>
        <p className="max-w-md text-sm text-text-secondary">
          The agent picks which tools it actually needs — documentation search,
          live statistics, recent code changes — and shows its work below each
          answer.
        </p>
      </div>
      <div className="flex w-full max-w-md flex-col gap-2">
        {EXAMPLE_QUESTIONS.map((question) => (
          <button
            key={question}
            type="button"
            onClick={() => onSelectExample(question)}
            className="rounded-lg border border-border bg-surface px-4 py-2.5 text-left text-sm text-text-secondary transition hover:border-accent hover:text-text-primary"
          >
            {question}
          </button>
        ))}
      </div>
    </div>
  );
}
