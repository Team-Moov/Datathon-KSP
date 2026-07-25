import * as React from "react"

import { streamChatTurn, exportConversationPdf, type ChatLanguage, type ChatMessage } from "./chatApi"
import type { ChatSuggestion } from "@/lib/types/api"
import { useVoiceLiveSession } from "./useVoiceLiveSession"

export interface ToolActivityEntry {
  tool: string
  status: string
}

export interface TraceEntry {
  tool: string
  // inputs are intentionally omitted from the frontend trace — the backend
  // already enforces RBAC on what data is visible; raw tool args (case IDs,
  // person IDs) are never sent to the frontend to avoid a secondary
  // exfiltration path for users whose role doesn't have direct access to
  // those identifiers.
  durationMs?: number
  status: "ok" | "error"
}

export interface WidgetEntry {
  widgetType: string
  data: unknown
}

export interface ConversationTurn {
  id: string
  role: "user" | "assistant"
  content: string
  toolActivity: ToolActivityEntry[]
  trace: TraceEntry[]
  widgets: WidgetEntry[]
  suggestions: ChatSuggestion[]
  isAiUnavailable: boolean
  isStreaming: boolean
}

function createTurnId(): string {
  return crypto.randomUUID()
}

// Module-level state to persist chat across tab switches (unmount/remount)
// until a full page refresh.
let globalTurns: ConversationTurn[] = []
let globalSessionId = createTurnId()

export function useChatSession() {
  const [turns, _setTurns] = React.useState<ConversationTurn[]>(globalTurns)
  const [isAwaitingResponse, setIsAwaitingResponse] = React.useState(false)
  const [language, setLanguage] = React.useState<ChatLanguage>("en")
  const sessionIdRef = React.useRef(globalSessionId)
  const abortControllerRef = React.useRef<AbortController | null>(null)

  const setTurns = React.useCallback((action: React.SetStateAction<ConversationTurn[]>) => {
    _setTurns((prev) => {
      const next = typeof action === "function" ? action(prev) : action
      globalTurns = next
      return next
    })
  }, [])

  const resetChat = React.useCallback(() => {
    globalTurns = []
    globalSessionId = createTurnId()
    sessionIdRef.current = globalSessionId
    _setTurns([])
    setIsAwaitingResponse(false)
    abortControllerRef.current?.abort()
  }, [])

  function updateAssistantTurn(turnId: string, updater: (turn: ConversationTurn) => ConversationTurn) {
    setTurns((previous) => previous.map((turn) => (turn.id === turnId ? updater(turn) : turn)))
  }

  async function submitUserMessage(content: string) {
    const trimmed = content.trim()
    if (!trimmed || isAwaitingResponse) return

    const priorMessages: ChatMessage[] = turns.map((turn) => ({ role: turn.role, content: turn.content }))
    const userTurn: ConversationTurn = {
      id: createTurnId(),
      role: "user",
      content: trimmed,
      toolActivity: [],
      trace: [],
      widgets: [],
      suggestions: [],
      isAiUnavailable: false,
      isStreaming: false,
    }
    const assistantTurnId = createTurnId()
    const assistantTurn: ConversationTurn = {
      id: assistantTurnId,
      role: "assistant",
      content: "",
      toolActivity: [],
      trace: [],
      widgets: [],
      suggestions: [],
      isAiUnavailable: false,
      isStreaming: true,
    }

    setTurns((previous) => [...previous, userTurn, assistantTurn])
    setIsAwaitingResponse(true)

    const abortController = new AbortController()
    abortControllerRef.current = abortController

    try {
      for await (const event of streamChatTurn(
        sessionIdRef.current,
        [...priorMessages, { role: "user", content: trimmed }],
        abortController.signal,
        language,
      )) {
        if (event.type === "token" && event.content) {
          updateAssistantTurn(assistantTurnId, (turn) => ({ ...turn, content: turn.content + event.content }))
        } else if (event.type === "tool_call" && event.tool && event.status) {
          updateAssistantTurn(assistantTurnId, (turn) => ({
            ...turn,
            toolActivity: [...turn.toolActivity, { tool: event.tool!, status: event.status! }],
          }))
        } else if (event.type === "tool_result" && event.tool) {
          // Capture deterministic tool results into the per-turn trace.
          // We record only the tool name and status — raw args/results (which
          // may contain case/person IDs outside the user's normal access path)
          // are intentionally NOT forwarded to the frontend.
          updateAssistantTurn(assistantTurnId, (turn) => ({
            ...turn,
            trace: [
              ...turn.trace,
              {
                tool: event.tool!,
                status: (event.error ? "error" : "ok") as "ok" | "error",
              },
            ],
          }))
        } else if (event.type === "widget" && event.widget_type) {
          updateAssistantTurn(assistantTurnId, (turn) => ({
            ...turn,
            widgets: [...turn.widgets, { widgetType: event.widget_type!, data: event.data }],
          }))
        } else if (event.type === "suggestions" && event.items) {
          updateAssistantTurn(assistantTurnId, (turn) => ({ ...turn, suggestions: event.items! }))
        } else if (event.type === "error") {
          updateAssistantTurn(assistantTurnId, (turn) => ({
            ...turn,
            isAiUnavailable: event.error === "ai_unavailable",
            content: turn.content || event.message || "Something went wrong while generating this response.",
          }))
        }
      }
    } catch (error) {
      if (!abortController.signal.aborted) {
        updateAssistantTurn(assistantTurnId, (turn) => ({
          ...turn,
          isAiUnavailable: true,
          content: turn.content || "Couldn't reach the assistant. Check your connection and try again.",
        }))
      }
    } finally {
      updateAssistantTurn(assistantTurnId, (turn) => ({ ...turn, isStreaming: false }))
      setIsAwaitingResponse(false)
    }
  }

  function cancelActiveStream() {
    abortControllerRef.current?.abort()
  }

  async function exportConversation() {
    const messages: ChatMessage[] = turns.map((turn) => {
      let content = turn.content || ""
      if (turn.widgets && turn.widgets.length > 0) {
        content += "\n\n--- Technical Data (Widgets) ---\n"
        turn.widgets.forEach((w) => {
          content += `\nWidget: ${w.widgetType}\n${JSON.stringify(w.data, null, 2)}\n`
        })
      }
      return { role: turn.role, content }
    })
    if (messages.length === 0) return
    await exportConversationPdf(sessionIdRef.current, messages, language)
  }

  const voiceSession = useVoiceLiveSession(setTurns, language)

  return {
    turns,
    isAwaitingResponse,
    language,
    setLanguage,
    submitUserMessage,
    cancelActiveStream,
    exportConversation,
    resetChat,
    isVoiceSessionActive: voiceSession.isSessionActive,
    isVoiceConnecting: voiceSession.isConnecting,
    isVoiceSpeaking: voiceSession.isSpeaking,
    startVoiceSession: voiceSession.startVoiceSession,
    stopVoiceSession: voiceSession.stopVoiceSession,
  }
}
