interface PredictedLink {
  predicted_person_id: string
  name: string
  confidence: number
  source_tool: string
}

/**
 * Every row here is a lead, not a fact — confidence + source tool stay visible
 * next to each name so this never reads like a confirmed relationship (§4/§11).
 */
function PredictedLinksList({ links }: { links: PredictedLink[] }) {
  if (links.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No predicted links surfaced.</p>
  }
  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {links.map((link) => (
        <li key={link.predicted_person_id} className="flex items-center justify-between px-3 py-2 text-xs">
          <div>
            <p className="font-medium text-zinc-800 dark:text-zinc-100">{link.name || link.predicted_person_id}</p>
            <p className="text-[10px] text-zinc-400">{link.source_tool} · PREDICTED (unverified)</p>
          </div>
          <span className="shrink-0 rounded-full bg-caution-500/10 px-2 py-0.5 text-[10px] font-medium text-caution-600 dark:text-caution-400">
            {Math.round(link.confidence * 100)}%
          </span>
        </li>
      ))}
    </ul>
  )
}

export { PredictedLinksList }
export type { PredictedLink }
