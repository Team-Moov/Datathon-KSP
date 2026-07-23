import { CaseTimeline, type TimelineEvent } from "@/components/charts/CaseTimeline"

interface CaseBriefLead {
  type: string
  person_id?: string
  name?: string
  confidence?: number
  source_tool?: string
  label?: string
}

interface CaseBriefSimilarCase {
  case_id: string
  crime_no: string
  date_reported: string
  disposition: string | null
  brief_facts_snippet: string
}

interface CaseBrief {
  case_id: string
  context_summary: string
  timeline: TimelineEvent[]
  similar_cases: CaseBriefSimilarCase[]
  leads: CaseBriefLead[]
  disclaimer: string
}

/** The one-click investigator case brief (§8.1) — fixed fan-out of timeline,
 * similar-case RAG, and deterministic-tool leads, merged for display. Every
 * lead/similar-case here came from a named tool, never free LLM recall. */
function CaseBriefCard({ brief }: { brief: CaseBrief }) {
  return (
    <div className="space-y-3">
      <p className="text-sm text-zinc-700 dark:text-zinc-300">{brief.context_summary}</p>

      <CaseTimeline timeline={brief.timeline} />

      {brief.leads.length > 0 ? (
        <div className="flat-surface rounded-md p-3">
          <p className="section-label mb-1.5">Leads</p>
          <ul className="space-y-1.5">
            {brief.leads.map((lead, index) => (
              <li key={index} className="flex items-center justify-between text-xs">
                <span className="text-zinc-700 dark:text-zinc-300">{lead.name ?? lead.person_id ?? lead.type}</span>
                <span className="text-[10px] text-zinc-400">
                  {lead.source_tool} {lead.confidence !== undefined ? `· ${Math.round(lead.confidence * 100)}%` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {brief.similar_cases.length > 0 ? (
        <div className="flat-surface rounded-md p-3">
          <p className="section-label mb-1.5">Similar cases</p>
          <ul className="space-y-1.5">
            {brief.similar_cases.map((similar) => (
              <li key={similar.case_id} className="text-xs">
                <span className="font-mono text-zinc-700 dark:text-zinc-300">{similar.crime_no}</span>
                <span className="ml-2 text-[10px] text-zinc-400">{similar.disposition ?? "status unknown"}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <p className="text-[11px] italic text-zinc-400 dark:text-zinc-600">{brief.disclaimer}</p>
    </div>
  )
}

export { CaseBriefCard }
export type { CaseBrief }
