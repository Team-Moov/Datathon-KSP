import { Badge } from "@/components/ui/badge"
import { CaseTimeline, type TimelineEvent } from "@/components/charts/CaseTimeline"

interface CaseWorkspaceSummary {
  case: {
    id: string
    crime_no: string
    date_reported: string | null
    district_id: number | null
    case_status_id: number | null
    brief_facts: string | null
    disposition: string | null
    version: number
  }
  people: Record<string, { person_id: string; name: string; human_verified: boolean; arrested: boolean }[]>
  documents: { document_id: string; original_filename: string; source_type: string }[]
  timeline: TimelineEvent[]
  notes: unknown[]
}

/** Compact read-only view of the full investigator workspace (§ Investigator
 * Workspace) for the chat assistant — same masked data the dedicated
 * /cases/:caseId page shows, condensed for the conversation thread. */
function CaseWorkspaceSummaryCard({ workspace }: { workspace: CaseWorkspaceSummary }) {
  const peopleCount = Object.values(workspace.people).reduce((sum, group) => sum + group.length, 0)

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="font-mono text-sm font-semibold text-zinc-900 dark:text-zinc-50">{workspace.case.crime_no}</h3>
          {workspace.case.disposition ? <Badge variant="neutral">{workspace.case.disposition}</Badge> : null}
        </div>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Reported {workspace.case.date_reported ?? "date unknown"} · District {workspace.case.district_id ?? "-"} · {peopleCount}{" "}
          {peopleCount === 1 ? "person" : "people"} · {workspace.documents.length} documents
        </p>
        {workspace.case.brief_facts ? (
          <p className="mt-1 text-sm text-zinc-700 dark:text-zinc-300">{workspace.case.brief_facts}</p>
        ) : (
          <p className="mt-1 text-sm italic text-zinc-400 dark:text-zinc-600">Brief facts are restricted for your access level.</p>
        )}
      </div>

      <CaseTimeline timeline={workspace.timeline} />
    </div>
  )
}

export { CaseWorkspaceSummaryCard }
export type { CaseWorkspaceSummary }
