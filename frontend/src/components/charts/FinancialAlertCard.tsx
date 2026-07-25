import { Info } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { FinancialFlowDiagram } from "@/components/charts/FinancialFlowDiagram"
import { Badge } from "@/components/ui/badge"

interface SuspiciousTransactionAlert {
  typology: string
  accounts_involved: string[]
  evidence_trail: Record<string, unknown>
  confidence: number
  recommended_action: string
  disclaimer: string
}

/** Shared alert card — used on the dedicated Financial Crime page and reused
 * for the chat flow_diagram widget so the two never drift into two renderings
 * of the same STR-shaped alert object. */
function FinancialAlertCard({ alert }: { alert: SuspiciousTransactionAlert }) {
  return (
    <div className="flat-surface space-y-3 rounded-md p-4">
      <div className="flex items-center justify-between">
        <Badge variant="critical">{alert.typology}</Badge>
        <div className="flex items-center gap-1">
          <span className="text-xs text-zinc-500">{Math.round(alert.confidence * 100)}% confidence</span>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300">
                  <Info className="w-3 h-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p className="text-xs">Model confidence score indicating the probability that this alert matches a known suspicious transaction pattern (0-100%)</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
      <FinancialFlowDiagram accountsInvolved={alert.accounts_involved} />
      <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        {Object.entries(alert.evidence_trail).map(([key, value]) => (
          <div key={key}>
            <dt className="text-zinc-400">{key.replace(/_/g, " ")}</dt>
            <dd className="text-zinc-700 dark:text-zinc-300">{String(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{alert.recommended_action}</p>
      <p className="text-[11px] italic text-zinc-400 dark:text-zinc-600">{alert.disclaimer}</p>
    </div>
  )
}

export { FinancialAlertCard }
export type { SuspiciousTransactionAlert }
