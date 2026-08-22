"""Minimal, standalone OpenRouter chat-completion client for evaluation
scripts.

Deliberately does NOT import `backend.app.llm.openrouter_provider` —
`evaluation/` is meant to be a standalone tool runnable against any
deployment of this project, even one where `backend/` isn't importable
from wherever this is run. It duplicates the minimal amount of
OpenRouter-calling logic it actually needs (a single non-tool-calling
completion, for the single-shot RAG baseline) rather than reaching into
the backend package.
"""

from __future__ import annotations

import httpx


async def simple_chat_completion(
    api_key: str,
    model: str,
    system_prompt: str,
    user_message: str,
    base_url: str = "https://openrouter.ai/api/v1",
    timeout_seconds: float = 60.0,
) -> str:
    async with httpx.AsyncClient(
        base_url=base_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout_seconds
    ) as client:
        response = await client.post(
            "/chat/completions",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"] or ""
