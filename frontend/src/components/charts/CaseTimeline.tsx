import * as React from "react"
import { ChevronRight, CircleDot, FileText } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

const STAGE_LABELS: Record<string, string> = {
  registered: "Registered",
  investigation: "Under Investigation",
  chargesheet_filed: "Chargesheet Filed",
  disposed: "Disposed",
  closed: "Closed",
}

interface TimelineEvent {
  stage: string
  event_date: string
  confidence: number
  source_document_id?: string | null
}

/**
 * Shared by both timeline producers (workspace_service.build_case_workspace
 * and investigator_support._timeline_brief) — a broader local shape than
 * CaseWorkspaceSnapshot["timeline"] since the case-brief path also carries
 * source_document_id, which the workspace path doesn't. Lives under
 * components/charts (not features/cases) because it's reused by the chat
 * widget catalog (CaseBriefCard, CaseWorkspaceSummaryCard) as well as the
 * case workspace page.
 *
 * Entries with a source document expand inline to show the reference on
 * click — there's no dedicated document-viewer route yet to navigate to, so
 * this is the honest version of "interactive" rather than a link to a page
 * that doesn't exist.
 */
function CaseTimeline({ timeline }: { timeline: TimelineEvent[] }) {
  const [expandedIndex, setExpandedIndex] = React.useState<number | null>(null)

  return (
    <Card>
      <CardHeader>
        <CardTitle>Timeline</CardTitle>
      </CardHeader>
      <CardContent>
        {timeline.length === 0 ? (
          <EmptyState title="No stage events recorded yet" />
        ) : (
          <ol className="space-y-3 border-l border-zinc-200 pl-4 dark:border-zinc-800">
            {timeline.map((event, index) => {
              const hasSource = Boolean(event.source_document_id)
              const isExpanded = expandedIndex === index
              return (
                <li key={`${event.stage}-${event.event_date}-${index}`} className="relative">
                  <CircleDot className="absolute -left-[21px] top-0.5 size-3 text-accent-600 dark:text-accent-300" />
                  <button
                    type="button"
                    disabled={!hasSource}
                    onClick={() => setExpandedIndex(isExpanded ? null : index)}
                    className={cn(
                      "flex w-full items-start justify-between gap-2 text-left",
                      hasSource ? "cursor-pointer" : "cursor-default",
                    )}
                  >
                    <div>
                      <p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
                        {STAGE_LABELS[event.stage] ?? event.stage}
                      </p>
                      <p className="text-xs text-zinc-500 dark:text-zinc-400">
                        {event.event_date} · confidence {Math.round(event.confidence * 100)}%
                      </p>
                    </div>
                    {hasSource ? (
                      <ChevronRight className={cn("mt-0.5 size-3.5 shrink-0 text-zinc-400 transition-transform", isExpanded && "rotate-90")} />
                    ) : null}
                  </button>
                  {isExpanded && event.source_document_id ? (
                    <div className="mt-1.5 flex items-center gap-1.5 rounded-md bg-zinc-50 px-2 py-1.5 text-[11px] text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400">
                      <FileText className="size-3" />
                      <span>Source document: </span>
                      <span className="font-mono">{event.source_document_id}</span>
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

export { CaseTimeline }
export type { TimelineEvent }
