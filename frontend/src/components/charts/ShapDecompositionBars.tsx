import { Info } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

const FEATURE_LABELS: Record<string, { label: string; description: string }> = {
  // Keys as the trained survival model / ML bridge actually writes them.
  severity_history: {
    label: "Severity-weighted history (CHI)",
    description: "Central Eight factor: severity-weighted harm history quantifying past criminal involvement",
  },
  centrality: {
    label: "Network position",
    description: "Network centrality score showing how central this person is within their criminal network",
  },
  mo_consistency: {
    label: "MO consistency / escalation",
    description: "Modus operandi similarity across cases and evidence of escalation in crime patterns",
  },
  associate_risk: {
    label: "Associate risk",
    description: "Risk inherited from associates and network connections with higher-risk individuals",
  },
  // Legacy ORM-column aliases (kept so older rows still render with real labels).
  chi_weighted_harm: {
    label: "Severity-weighted history (CHI)",
    description: "Central Eight factor: severity-weighted harm history quantifying past criminal involvement",
  },
  network_centrality: {
    label: "Network position",
    description: "Network centrality score showing how central this person is within their criminal network",
  },
  mo_escalation_score: {
    label: "MO consistency / escalation",
    description: "Modus operandi similarity across cases and evidence of escalation in crime patterns",
  },
  associate_risk_avg: {
    label: "Associate risk",
    description: "Risk inherited from associates and network connections with higher-risk individuals",
  },
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
        const featureInfo = FEATURE_LABELS[feature] || { label: feature, description: "Feature contribution to risk score" }
        return (
          <div key={feature}>
            <div className="mb-0.5 flex items-center justify-between text-xs">
              <div className="flex items-center gap-1">
                <span className="text-zinc-600 dark:text-zinc-300">{featureInfo.label}</span>
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300">
                        <Info className="w-3 h-3" />
                      </button>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="text-xs">{featureInfo.description}</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              </div>
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
