import { httpClient } from "@/lib/api/httpClient"
import { getAccessToken } from "@/lib/api/authTokenStore"
import type { ChatStreamEvent } from "@/lib/types/api"

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
}

/**
 * Export the conversation transcript to a watermarked PDF (backend /chat/export,
 * rendered via the configured PdfRenderer) and trigger a browser download.
 * Satisfies the PS requirement to save conversation history locally as PDF.
 */
export async function exportConversationPdf(sessionId: string, messages: ChatMessage[]): Promise<void> {
  const response = await httpClient.post(
    "/chat/export",
    { session_id: sessionId, messages, language: "en" },
    { responseType: "blob" },
  )
  const url = URL.createObjectURL(response.data as Blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = `chat_${sessionId}.pdf`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
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
