import { CircleDot } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { CaseWorkspaceSnapshot } from "@/lib/types/api"

const STAGE_LABELS: Record<string, string> = {
  registered: "Registered",
  investigation: "Under Investigation",
  chargesheet_filed: "Chargesheet Filed",
  disposed: "Disposed",
  closed: "Closed",
}

function CaseTimeline({ timeline }: { timeline: CaseWorkspaceSnapshot["timeline"] }) {
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
            {timeline.map((event, index) => (
              <li key={`${event.stage}-${event.event_date}-${index}`} className="relative">
                <CircleDot className="absolute -left-[21px] top-0.5 size-3 text-accent-600 dark:text-accent-300" />
                <p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">
                  {STAGE_LABELS[event.stage] ?? event.stage}
                </p>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {event.event_date} · confidence {Math.round(event.confidence * 100)}%
                </p>
              </li>
            ))}
          </ol>
        )}
      </CardContent>
    </Card>
  )
}

export { CaseTimeline }
