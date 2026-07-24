export interface SurveillanceCheckpoint {
  rank: number
  lat: number
  lng: number
  predicted_rate: number
  background_component: number
  near_repeat_component: number
  priority_tier: "High" | "Medium" | "Low"
  dominant_driver: string
}

export interface SurveillancePrioritiesData {
  status: "ok" | "insufficient_data"
  target_date: string
  total_cells_forecast: number
  checkpoints: SurveillanceCheckpoint[]
  chronic_vs_acute: { chronic_pct: number; acute_pct: number } | null
}

const TIER_STYLES: Record<SurveillanceCheckpoint["priority_tier"], string> = {
  High: "bg-critical-500/10 text-critical-600 dark:text-critical-400",
  Medium: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
  Low: "bg-zinc-500/10 text-zinc-500 dark:text-zinc-400",
}

/** Ranked, real hotspot-forecast grid cells — a priority list for where to look,
 * not a shift roster or named-unit assignment (no such data exists in this system). */
function SurveillancePriorityList({ data }: { data: SurveillancePrioritiesData }) {
  if (data.checkpoints.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No forecast data available to rank for this district/date.</p>
  }
  return (
    <div className="space-y-3">
      {data.chronic_vs_acute ? (
        <div className="flex items-center gap-4 rounded-md bg-zinc-50 dark:bg-zinc-800/50 px-3 py-2 text-xs">
          <span className="font-medium text-zinc-700 dark:text-zinc-300">
            Chronic (baseline): {data.chronic_vs_acute.chronic_pct}%
          </span>
          <span className="font-medium text-zinc-700 dark:text-zinc-300">
            Acute (near-repeat): {data.chronic_vs_acute.acute_pct}%
          </span>
          <span className="text-zinc-400">across {data.total_cells_forecast} forecast cells</span>
        </div>
      ) : null}
      <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
        {data.checkpoints.map((cp) => (
          <li key={cp.rank} className="flex items-center justify-between px-3 py-2 text-xs">
            <div>
              <p className="font-medium text-zinc-800 dark:text-zinc-100">
                #{cp.rank} · {cp.lat.toFixed(4)}, {cp.lng.toFixed(4)}
              </p>
              <p className="text-[10px] text-zinc-400">{cp.dominant_driver}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[10px] text-zinc-500">rate {cp.predicted_rate.toFixed(3)}</span>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${TIER_STYLES[cp.priority_tier]}`}>
                {cp.priority_tier}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}

export { SurveillancePriorityList }
