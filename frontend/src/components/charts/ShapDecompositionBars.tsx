import { cn } from "@/lib/utils"

const FEATURE_LABELS: Record<string, string> = {
  chi_weighted_harm: "Severity-weighted history (CHI)",
  network_centrality: "Network position",
  mo_escalation_score: "MO consistency / escalation",
  associate_risk_avg: "Associate risk",
}

/** Never a bare score — every risk number ships with this breakdown alongside it. */
function ShapDecompositionBars({ decomposition }: { decomposition: Record<string, number> }) {
  const entries = Object.entries(decomposition)
  const maxMagnitude = Math.max(...entries.map(([, value]) => Math.abs(value)), 0.01)

  return (
    <div className="space-y-2">
      {entries.map(([feature, contribution]) => {
        const widthPct = (Math.abs(contribution) / maxMagnitude) * 100
        const isNegative = contribution < 0
        return (
          <div key={feature}>
            <div className="mb-0.5 flex items-center justify-between text-xs">
              <span className="text-zinc-600 dark:text-zinc-300">{FEATURE_LABELS[feature] ?? feature}</span>
              <span className={cn("font-mono", isNegative ? "text-critical-500" : "text-affirm-600 dark:text-affirm-500")}>
                {contribution > 0 ? "+" : ""}
                {contribution.toFixed(2)}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
              <div
                style={{ width: `${widthPct}%` }}
                className={cn("h-full rounded-full", isNegative ? "bg-critical-500" : "bg-affirm-500")}
              />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export { ShapDecompositionBars }
