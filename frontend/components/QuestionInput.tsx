"use client";

import { FormEvent, KeyboardEvent, useState } from "react";

// Matches backend/app/api/chat.py's ChatRequest.message max_length
// exactly — enforced here too so the person gets feedback before
// submitting, not just a 422 after the fact.
const MAX_LENGTH = 2000;

interface QuestionInputProps {
  onSubmit: (question: string) => void;
  disabled: boolean;
}

export function QuestionInput({ onSubmit, disabled }: QuestionInputProps) {
  const [value, setValue] = useState("");

  function submit() {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setValue("");
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  const nearLimit = value.length > MAX_LENGTH - 200;

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-1.5">
      <div className="flex items-end gap-2">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={1}
          maxLength={MAX_LENGTH}
          placeholder="Ask about an incident, a metric, or a recent change…"
          aria-label="Ask the agent a question"
          className="max-h-40 min-h-[44px] flex-1 resize-none rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-text-primary placeholder:text-text-tertiary focus:border-accent disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || value.trim().length === 0}
          className="h-[44px] shrink-0 rounded-lg bg-accent px-4 text-sm font-medium text-bg transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {disabled ? "Investigating…" : "Ask"}
        </button>
      </div>
      {nearLimit && (
        <span className="self-end font-mono text-xs text-text-tertiary">
          {value.length}/{MAX_LENGTH}
        </span>
      )}
    </form>
  );
}
