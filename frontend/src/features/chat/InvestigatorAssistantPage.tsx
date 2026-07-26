import * as React from "react"
import { ChevronDown, ChevronUp, Download, Loader2, Mic, MicOff, MessagesSquare, RotateCcw, SendHorizontal, Volume2, WifiOff, X } from "lucide-react"
import { useTranslation } from "react-i18next"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { cn } from "@/lib/utils"
import type { ChatLanguage } from "./chatApi"
import { ChatWidgetRenderer } from "./ChatWidgetRenderer"
import { type ConversationTurn, type TraceEntry, useChatSession } from "./useChatSession"
import { MarkdownRenderer } from "@/components/ui/MarkdownRenderer"

// Human-readable labels for each tool name. Keys are the raw function names
// from the backend tool catalog. Unlisted tools fall back to the raw name
// with underscores replaced by spaces.
const TOOL_LABELS: Record<string, string> = {
  get_graph_subset: "Fetch network subgraph",
  compute_centrality: "Compute centrality scores",
  detect_organized_groups: "Detect organized groups",
  predict_links: "Predict network links",
  multi_jurisdiction_offenders: "Find multi-jurisdiction offenders",
  run_hawkes_forecast: "Run Hawkes/ETAS forecast",
  get_temporal_trends: "Fetch temporal seasonality data",
  rank_surveillance_priorities: "Rank surveillance priorities",
  detect_financial_structuring: "Detect financial structuring",
  detect_funnel_accounts: "Detect funnel/mule accounts",
  detect_layering_cycles: "Detect layering cycles",
  detect_financial_clusters: "Detect organized financial clusters",
  compute_risk_score: "Compute person risk score",
  search_persons: "Search persons by name",
  get_case_details: "Fetch case details",
  get_mo_linkage: "Find MO-linked cases",
  get_socio_economic_indicators: "Fetch socio-economic indicators",
  get_correlation_matrix: "Compute correlation matrix",
  get_gwr_results: "Fetch GWR spatial model results",
  get_victim_demographics: "Fetch victim demographics",
  get_urbanization_impact: "Fetch urbanization impact data",
  get_policy_recommendations: "Generate policy recommendations",
  get_crime_statistics: "Fetch crime statistics",
  scan_financial_typologies: "Full financial typology scan",
}

// ── Animated waveform bars shown when Gemini is speaking ─────────────────────
function SpeakingWaveform() {
  const { t } = useTranslation()
  return (
    <span className="inline-flex items-end gap-[3px]" aria-label={t("chat.geminiSpeaking")}>
      {[0, 1, 2, 3, 4].map((i) => (
        <span
          key={i}
          className="block w-[3px] rounded-full bg-accent-500"
          style={{
            height: "14px",
            animation: `voiceBar 0.9s ease-in-out ${i * 0.12}s infinite alternate`,
          }}
        />
      ))}
    </span>
  )
}

// ── Pulsing mic ring shown when session is active and listening ───────────────
function MicPulseRing({ active }: { active: boolean }) {
  if (!active) return null
  return (
    <span className="relative flex size-3">
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-red-400 opacity-75" />
      <span className="relative inline-flex size-3 rounded-full bg-red-500" />
    </span>
  )
}

// ── Live voice session banner ─────────────────────────────────────────────────
function VoiceBanner({
  isSpeaking,
  onStop,
}: {
  isSpeaking: boolean
  onStop: () => void
}) {
  const { t } = useTranslation()
  return (
    <div
      className={cn(
        "flex items-center justify-between gap-3 rounded-lg border px-4 py-2.5 text-sm transition-colors",
        isSpeaking
          ? "border-accent-400/50 bg-accent-500/10 text-accent-700 dark:border-accent-400/40 dark:bg-accent-500/15 dark:text-accent-300"
          : "border-red-400/40 bg-red-500/10 text-red-700 dark:border-red-400/30 dark:bg-red-500/10 dark:text-red-400",
      )}
    >
      <div className="flex items-center gap-2.5">
        {isSpeaking ? (
          <>
            <Volume2 className="size-4 shrink-0" />
            <span className="font-medium">{t("chat.geminiSpeaking")}</span>
            <SpeakingWaveform />
          </>
        ) : (
          <>
            <MicPulseRing active />
            <span className="font-medium">{t("chat.listening")}</span>
            <span className="text-xs text-zinc-500 dark:text-zinc-400">{t("chat.speakYourQuestion")}</span>
          </>
        )}
      </div>
      <button
        type="button"
        onClick={onStop}
        className="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium opacity-70 transition-opacity hover:opacity-100"
        title={t("chat.endVoiceSession")}
      >
        <X className="size-3.5" />
        {t("chat.endSession")}
      </button>
    </div>
  )
}

// ── Tool activity chips (during streaming) ────────────────────────────────────
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

// ── Tool-call trace panel (after response completes) ─────────────────────────
function TracePanel({
  trace,
  originalQuery,
}: {
  trace: TraceEntry[]
  originalQuery: string | undefined
}) {
  const { t } = useTranslation()
  const [open, setOpen] = React.useState(false)

  // Only show the panel for assistant turns that have at least one recorded
  // tool result, or explicitly had no tools called (to confirm that too).
  // Don't show it while streaming is still in progress (caller gates this).
  return (
    <div className="mt-1">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="inline-flex items-center gap-1 text-[11px] text-zinc-400 hover:text-zinc-600 dark:text-zinc-600 dark:hover:text-zinc-400 transition-colors"
        aria-expanded={open}
      >
        {open ? <ChevronUp className="size-3" /> : <ChevronDown className="size-3" />}
        {open ? t("chatTrace.hideDetails") : t("chatTrace.showDetails")}
      </button>

      {open && (
        <div className="mt-2 rounded-md border border-zinc-200 bg-zinc-50/80 p-3 text-xs dark:border-zinc-800 dark:bg-zinc-900/60">
          {/* Original query */}
          {originalQuery && (
            <div className="mb-2.5">
              <p className="mb-0.5 font-medium text-zinc-500 dark:text-zinc-400">
                {t("chatTrace.originalQuery")}
              </p>
              <p className="text-zinc-700 dark:text-zinc-300">{originalQuery}</p>
            </div>
          )}

          {/* Tool invocations */}
          <p className="mb-1.5 font-medium text-zinc-500 dark:text-zinc-400">
            {t("chatTrace.toolsInvoked")}
          </p>
          {trace.length === 0 ? (
            <p className="text-zinc-400 dark:text-zinc-600 italic">{t("chatTrace.noToolsCalled")}</p>
          ) : (
            <ol className="space-y-1">
              {trace.map((entry, i) => (
                <li key={i} className="flex items-center gap-2">
                  <span
                    className={cn(
                      "size-1.5 rounded-full shrink-0",
                      entry.status === "ok" ? "bg-emerald-500" : "bg-red-500",
                    )}
                  />
                  <span className="text-zinc-700 dark:text-zinc-300">
                    {TOOL_LABELS[entry.tool] ?? entry.tool.replace(/_/g, " ")}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </div>
      )}
    </div>
  )
}

// ── A single chat bubble ──────────────────────────────────────────────────────
function ConversationBubble({
  turn,
  onFollowUpQuery,
  originalQuery,
}: {
  turn: ConversationTurn
  onFollowUpQuery?: (query: string) => void
  originalQuery?: string
}) {
  const { t } = useTranslation()
  const isUser = turn.role === "user"
  return (
    <div className={cn("flex", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("max-w-2xl space-y-2", isUser ? "" : "w-full")}>
        {!isUser && turn.isStreaming ? <ToolActivityChips activity={turn.toolActivity} /> : null}

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
            <MarkdownRenderer content={turn.content} />
          ) : turn.isStreaming ? (
            <span className="inline-flex items-center gap-1 text-zinc-400">
              <Loader2 className="size-3.5 animate-spin" /> {t("chat.thinking")}
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

        {/* Tool-call trace panel — only shown for completed assistant turns */}
        {!isUser && !turn.isStreaming && (
          <TracePanel trace={turn.trace} originalQuery={originalQuery} />
        )}
      </div>
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────
function InvestigatorAssistantPage() {
  const { t } = useTranslation()
  const {
    turns,
    isAwaitingResponse,
    language,
    setLanguage,
    submitUserMessage,
    exportConversation,
    isVoiceSessionActive,
    isVoiceConnecting,
    isVoiceSpeaking,
    startVoiceSession,
    stopVoiceSession,
    resetChat,
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

  // Text input is locked while a voice session is active — mixing modes
  // mid-conversation confuses the session context.
  const isTextInputDisabled = isAwaitingResponse || isVoiceSessionActive

  return (
    <>
      {/* Keyframe for the speaking waveform bars — injected once per mount */}
      <style>{`
        @keyframes voiceBar {
          from { transform: scaleY(0.25); opacity: 0.5; }
          to   { transform: scaleY(1);    opacity: 1;   }
        }
      `}</style>

      <div className="flex h-[calc(100vh-7.5rem)] flex-col">
        {/* ── Header ── */}
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("nav.assistant")}</h1>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {t("chat.planDesc")}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <Select value={language} onValueChange={(value) => setLanguage(value as ChatLanguage)}>
              <SelectTrigger className="w-28" title={t("chat.replyLanguage")}>
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
              onClick={resetChat}
              disabled={turns.length === 0}
              className="gap-1.5"
              title={t("chat.resetChat")}
            >
              <RotateCcw className="size-4" />
              <span className="sr-only sm:not-sr-only">{t("chat.resetChat")}</span>
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={handleExport}
              disabled={turns.length === 0 || isExporting}
              className="gap-1.5"
              title={t("chat.saveAsPdf")}
            >
              {isExporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
              {t("chat.exportPdf")}
            </Button>
          </div>
        </div>

        {/* ── Live voice session banner (shown only when session is active) ── */}
        {isVoiceSessionActive && (
          <div className="mb-3">
            <VoiceBanner isSpeaking={isVoiceSpeaking} onStop={stopVoiceSession} />
          </div>
        )}

        {/* ── Conversation transcript ── */}
        <div className="flat-surface flex-1 space-y-4 overflow-y-auto rounded-lg p-4">
          {turns.length === 0 ? (
            <EmptyState
              icon={MessagesSquare}
              title={t("chat.emptyStateTitle")}
              description={t("chat.emptyStateDesc")}
            />
          ) : (
            turns.map((turn, index) => (
              <ConversationBubble
                key={turn.id}
                turn={turn}
                // Pass the preceding user message as the original query so
                // the trace panel can confirm what was interpreted.
                originalQuery={
                  turn.role === "assistant" && index > 0 && turns[index - 1].role === "user"
                    ? turns[index - 1].content
                    : undefined
                }
                onFollowUpQuery={isAwaitingResponse ? undefined : (query) => void submitUserMessage(query)}
              />
            ))
          )}
          <div ref={scrollAnchorRef} />
        </div>

        {/* ── Input bar ── */}
        <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
          <input
            value={draftMessage}
            onChange={(event) => setDraftMessage(event.target.value)}
            placeholder={
              isVoiceSessionActive
                ? t("chat.voiceSessionActivePlaceholder")
                : t("chat.typeQuestionPlaceholder")
            }
            disabled={isTextInputDisabled}
            className="flex-1 rounded-md border border-zinc-300 bg-white px-3 text-sm text-zinc-900 outline-none focus-visible:border-accent-400 focus-visible:ring-2 focus-visible:ring-accent-400/30 disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
          />

          {/* Voice toggle button */}
          <Button
            type="button"
            variant={isVoiceSessionActive ? "destructive" : "outline"}
            onClick={() => (isVoiceSessionActive ? stopVoiceSession() : void startVoiceSession())}
            disabled={isVoiceConnecting}
            className={cn(
              "gap-1.5 transition-all",
              isVoiceSessionActive && !isVoiceSpeaking && "animate-pulse",
            )}
            title={isVoiceSessionActive ? t("chat.endLiveVoice") : t("chat.startLiveVoice")}
          >
            {isVoiceConnecting ? (
              <Loader2 className="size-4 animate-spin" />
            ) : isVoiceSessionActive ? (
              <MicOff className="size-4" />
            ) : (
              <Mic className="size-4" />
            )}
            {isVoiceConnecting ? t("chat.connectingEllipsis") : isVoiceSessionActive ? t("chat.endVoice") : t("chat.voice")}
          </Button>

          {/* Send button — hidden while voice session is active */}
          {!isVoiceSessionActive && (
            <Button type="submit" disabled={isAwaitingResponse || !draftMessage.trim()} className="gap-1.5">
              <SendHorizontal className="size-4" />
              {t("chat.send")}
            </Button>
          )}
        </form>
      </div>
    </>
  )
}

export { InvestigatorAssistantPage }
