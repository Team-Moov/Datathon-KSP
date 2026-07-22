import * as React from "react"
import { Download, Loader2, MessagesSquare, SendHorizontal, WifiOff } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
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

function ConversationBubble({ turn }: { turn: ConversationTurn }) {
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
          <ChatWidgetRenderer key={index} widget={widget} />
        ))}
      </div>
    </div>
  )
}

function InvestigatorAssistantPage() {
  const { turns, isAwaitingResponse, submitUserMessage, exportConversation } = useChatSession()
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
        <Button
          type="button"
          variant="outline"
          onClick={handleExport}
          disabled={turns.length === 0 || isExporting}
          className="shrink-0 gap-1.5"
          title="Save this conversation as a PDF"
        >
          {isExporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
          Export PDF
        </Button>
      </div>

      <div className="flat-surface flex-1 space-y-4 overflow-y-auto rounded-lg p-4">
        {turns.length === 0 ? (
          <EmptyState
            icon={MessagesSquare}
            title="Ask about a case, person, or pattern"
            description='Try "show the network for person X" or "forecast hotspots for district 3 next week."'
          />
        ) : (
          turns.map((turn) => <ConversationBubble key={turn.id} turn={turn} />)
        )}
        <div ref={scrollAnchorRef} />
      </div>

      <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
        <input
          value={draftMessage}
          onChange={(event) => setDraftMessage(event.target.value)}
          placeholder="Type a question..."
          disabled={isAwaitingResponse}
          className="flex-1 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-900 outline-none focus-visible:border-accent-400 focus-visible:ring-2 focus-visible:ring-accent-400/30 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <Button type="submit" disabled={isAwaitingResponse || !draftMessage.trim()} className="gap-1.5">
          <SendHorizontal className="size-4" />
          Send
        </Button>
      </form>
    </div>
  )
}

export { InvestigatorAssistantPage }
