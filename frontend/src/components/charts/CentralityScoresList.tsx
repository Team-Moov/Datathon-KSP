interface CentralityEntry {
  pagerank?: number
  betweenness?: number
}

/**
 * compute_centrality returns {person_id: {pagerank, betweenness}} — a metric
 * map, not a graph — so it renders as a ranked list rather than forcing it
 * through the force-directed graph widget, which needs actual node/edge shape.
 */
function CentralityScoresList({ scores }: { scores: Record<string, CentralityEntry> }) {
  const rows = Object.entries(scores).sort(([, a], [, b]) => (b.pagerank ?? 0) - (a.pagerank ?? 0))

  if (rows.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No centrality scores computed.</p>
  }

  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {rows.map(([personId, entry]) => (
        <li key={personId} className="flex items-center justify-between px-3 py-2 text-xs">
          <span className="truncate font-mono text-[11px] text-zinc-700 dark:text-zinc-300">{personId}</span>
          <span className="flex shrink-0 gap-3 text-[10px] text-zinc-500">
            <span>PageRank {(entry.pagerank ?? 0).toFixed(3)}</span>
            <span>Betweenness {(entry.betweenness ?? 0).toFixed(3)}</span>
          </span>
        </li>
      ))}
    </ul>
  )
}

export { CentralityScoresList }
