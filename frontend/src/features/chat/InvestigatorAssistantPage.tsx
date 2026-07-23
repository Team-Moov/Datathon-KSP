import * as React from "react"
import { Download, Loader2, Mic, MessagesSquare, SendHorizontal, WifiOff } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { ChatLanguage } from "./chatApi"
import { ChatWidgetRenderer } from "./ChatWidgetRenderer"
import { type ConversationTurn, useChatSession } from "./useChatSession"

function ToolActivityChips({ activity }: { activity: ConversationTurn["toolActivity"] }) {
  if (activity.length === 0) return null
  return (
    <div className="mb-2 flex flex-wrap gap-1.5">
      {activity.map((entry, index) => (
        <span
          key={`${entry.tool}-${index}`}
          className="inline-flex items-center gap-1 rounded-full border border-zinc-200 bg-zinc-50 px-2 py-0.5 text-[10px] text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400"
        >
          <Loader2 className="size-2.5 animate-spin" />
          {entry.tool.replace(/_/g, " ")}
        </span>
      ))}
    </div>
  )
}

function ConversationBubble({
  turn,
  onFollowUpQuery,
}: {
  turn: ConversationTurn
  onFollowUpQuery?: (query: string) => void
}) {
  const isUser = turn.role === "user"
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-2xl space-y-2", isUser ? "" : "w-full")}>
        {!isUser ? <ToolActivityChips activity={turn.toolActivity} /> : null}

        <div
          className={cn(
            "rounded-lg px-3.5 py-2.5 text-sm",
            isUser
              ? "bg-accent-600 text-white"
              : turn.isAiUnavailable
                ? "border border-caution-500/40 bg-caution-500/10 text-caution-600 dark:text-caution-500"
                : "flat-surface text-zinc-800 dark:text-zinc-100",
          )}
        >
          {turn.isAiUnavailable ? (
            <div className="flex items-start gap-2">
              <WifiOff className="mt-0.5 size-3.5 shrink-0" />
              <span>{turn.content}</span>
            </div>
          ) : turn.content ? (
            <p className="whitespace-pre-wrap">{turn.content}</p>
          ) : turn.isStreaming ? (
            <span className="inline-flex items-center gap-1 text-zinc-400">
              <Loader2 className="size-3.5 animate-spin" /> Thinking...
            </span>
          ) : null}
        </div>

        {turn.widgets.map((widget, index) => (
          <ChatWidgetRenderer key={index} widget={widget} onFollowUpQuery={onFollowUpQuery} />
        ))}

        {!isUser && turn.suggestions.length > 0 && onFollowUpQuery ? (
          <div className="flex flex-wrap gap-1.5 pt-0.5">
            {turn.suggestions.map((suggestion) => (
              <button
                key={suggestion.query}
                type="button"
                onClick={() => onFollowUpQuery(suggestion.query)}
                className="rounded-full border border-accent-300/60 bg-accent-500/5 px-2.5 py-0.5 text-[11px] text-accent-700 transition-colors hover:bg-accent-500/15 dark:border-accent-400/30 dark:text-accent-300"
                title={suggestion.query}
              >
                {suggestion.label}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  )
}

function InvestigatorAssistantPage() {
  const {
    turns,
    isAwaitingResponse,
    language,
    setLanguage,
    submitUserMessage,
    exportConversation,
    isVoiceSessionActive,
    isVoiceConnecting,
    startVoiceSession,
    stopVoiceSession,
  } = useChatSession()
  const [draftMessage, setDraftMessage] = React.useState("")
  const [isExporting, setIsExporting] = React.useState(false)
  const scrollAnchorRef = React.useRef<HTMLDivElement>(null)

  async function handleExport() {
    setIsExporting(true)
    try {
      await exportConversation()
    } finally {
      setIsExporting(false)
    }
  }

  React.useEffect(() => {
    scrollAnchorRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [turns])

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    const message = draftMessage
    setDraftMessage("")
    void submitUserMessage(message)
  }

  return (
    <div className="flex h-[calc(100vh-7.5rem)] flex-col">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Investigator Assistant</h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Plans which deterministic tool to run and narrates the result — every number comes from a tool output, never
            free recall.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Select value={language} onValueChange={(value) => setLanguage(value as ChatLanguage)}>
            <SelectTrigger className="w-28" title="Reply language">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="en">English</SelectItem>
              <SelectItem value="kn">ಕನ್ನಡ (Kannada)</SelectItem>
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant="outline"
            onClick={handleExport}
            disabled={turns.length === 0 || isExporting}
            className="gap-1.5"
            title="Save this conversation as a PDF"
          >
            {isExporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
            Export PDF
          </Button>
        </div>
      </div>

      <div className="flat-surface flex-1 space-y-4 overflow-y-auto rounded-lg p-4">
        {turns.length === 0 ? (
          <EmptyState
            icon={MessagesSquare}
            title="Ask about a case, person, or pattern"
            description='Try "show the network for person X" or "forecast hotspots for district 3 next week."'
          />
        ) : (
          turns.map((turn) => (
            <ConversationBubble
              key={turn.id}
              turn={turn}
              onFollowUpQuery={isAwaitingResponse ? undefined : (query) => void submitUserMessage(query)}
            />
          ))
        )}
        <div ref={scrollAnchorRef} />
      </div>

      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <input
          value={draftMessage}
          onChange={(event) => setDraftMessage(event.target.value)}
          placeholder="Type a question, or use the mic for a live voice conversation..."
          disabled={isAwaitingResponse}
          className="flex-1 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-900 outline-none focus-visible:border-accent-400 focus-visible:ring-2 focus-visible:ring-accent-400/30 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <Button
          type="button"
          variant={isVoiceSessionActive ? "destructive" : "outline"}
          onClick={() => (isVoiceSessionActive ? stopVoiceSession() : void startVoiceSession())}
          disabled={isVoiceConnecting}
          className="gap-1.5"
          title={isVoiceSessionActive ? "End live voice conversation" : "Start live voice conversation"}
        >
          {isVoiceConnecting ? <Loader2 className="size-4 animate-spin" /> : <Mic className="size-4" />}
          {isVoiceSessionActive ? "End voice" : "Voice"}
        </Button>
        <Button type="submit" disabled={isAwaitingResponse || !draftMessage.trim()} className="gap-1.5">
          <SendHorizontal className="size-4" />
          Send
        </Button>
      </form>
    </div>
  )
}

export { InvestigatorAssistantPage }
