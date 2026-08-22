import type { ChatResponse } from "./types";

export class ChatRequestError extends Error {}

/**
 * Calls this Next.js app's OWN `/api/chat` route — never the FastAPI
 * backend directly. The route handler (app/api/chat/route.ts) runs
 * server-side and is what actually holds the backend URL and (if
 * configured) the backend's shared API key; the browser never sees
 * either. See that file's docstring for the full reasoning.
 *
 * HTTP status codes are mapped to plain-language messages here, once,
 * so every caller gets consistent, honest copy — never a raw status
 * code or backend stack trace surfaced to the person using this.
 */
export async function askAgent(message: string): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
    });
  } catch {
    throw new ChatRequestError(
      "Couldn't reach the server. Check your connection and try again."
    );
  }

  if (response.ok) {
    return (await response.json()) as ChatResponse;
  }

  switch (response.status) {
    case 401:
      throw new ChatRequestError(
        "This console isn't authorized to reach the backend. Contact whoever set it up."
      );
    case 422:
      throw new ChatRequestError(
        "That question couldn't be sent as written — try rephrasing it."
      );
    case 429:
      throw new ChatRequestError(
        "Too many questions in a short time. Wait a moment and try again."
      );
    case 503:
      throw new ChatRequestError(
        "The agent isn't available right now — it may not be fully configured yet."
      );
    case 504:
      throw new ChatRequestError(
        "The investigation timed out before finishing. Try a narrower question."
      );
    default:
      throw new ChatRequestError(
        "Something went wrong on the server. Try again in a moment."
      );
  }
}
