import { Fingerprint } from "lucide-react"

export interface MoLinkageCluster {
  cluster_id: number | string
  case_count: number
  avg_similarity: number | null
}

/** Candidate same-offender crime series from the MO-linkage model (§5). Labeled
 * as plausible leads, never confirmed — similarity is behavioral, not evidential. */
function MoLinkageList({ clusters }: { clusters: MoLinkageCluster[] }) {
  if (clusters.length === 0) {
    return <p className="px-1 py-2 text-xs text-zinc-400">No MO series found above the similarity threshold.</p>
  }
  return (
    <ul className="space-y-1.5">
      {clusters.map((cluster) => (
        <li
          key={String(cluster.cluster_id)}
          className="flex items-center justify-between rounded-md border border-zinc-200 px-3 py-1.5 text-sm dark:border-zinc-800"
        >
          <span className="flex items-center gap-2 text-zinc-700 dark:text-zinc-200">
            <Fingerprint className="size-3.5 text-zinc-400" />
            Series #{cluster.cluster_id}
          </span>
          <span className="flex items-center gap-3 text-xs text-zinc-500 dark:text-zinc-400">
            <span>{cluster.case_count} cases</span>
            {typeof cluster.avg_similarity === "number" ? (
              <span className="font-mono">{(cluster.avg_similarity * 100).toFixed(0)}% MO match</span>
            ) : null}
          </span>
        </li>
      ))}
    </ul>
  )
}

export { MoLinkageList }
