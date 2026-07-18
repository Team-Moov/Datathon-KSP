import { getAccessToken } from "@/lib/api/authTokenStore"
import type { ChatStreamEvent } from "@/lib/types/api"

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

/**
 * Raw fetch + ReadableStream rather than axios — the /chat endpoint streams
 * newline-delimited JSON, and axios's browser adapter buffers the whole
 * response body before resolving, which defeats the point of streaming here.
 */
export async function* streamChatTurn(
  sessionId: string,
  messages: ChatMessage[],
  signal: AbortSignal,
): AsyncGenerator<ChatStreamEvent> {
  const response = await fetch("/api/v1/chat/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getAccessToken() ?? ""}`,
    },
    body: JSON.stringify({ session_id: sessionId, messages, language: "en" }),
    signal,
  })

  if (!response.ok || !response.body) {
    const errorBody = await response.text().catch(() => "")
    throw new Error(errorBody || `Chat request failed with status ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n")
    buffer = lines.pop() ?? ""

    for (const line of lines) {
      if (!line.trim()) continue
      yield JSON.parse(line) as ChatStreamEvent
    }
  }

  if (buffer.trim()) {
    yield JSON.parse(buffer) as ChatStreamEvent
  }
}
