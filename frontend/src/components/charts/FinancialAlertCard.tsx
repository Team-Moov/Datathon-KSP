import { Info, HelpCircle, CheckCircle2 } from "lucide-react"
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

const TYPOLOGY_EXPLANATIONS: Record<string, { title: string; description: string }> = {
  structuring: {
    title: "Structuring (Smurfing)",
    description: "Splitting a large financial transaction into multiple smaller transactions, each below the regulatory reporting threshold (e.g. 10 Lakhs INR), to evade detection by compliance teams and law enforcement."
  },
  funnel_account: {
    title: "Funnel Account (Money Mule)",
    description: "A technique where multiple cash deposits or electronic payments from unrelated source accounts are quickly funneled into a single destination account (fan-in), followed by a rapid withdrawal or transfer out (rapid emptying)."
  },
  layering_cycle: {
    title: "Layering Cycle (Circular Flow)",
    description: "Routing dirty money through a complex series of intermediate accounts in a closed loop, where funds eventually return to the origin node. This masks the source of funds and confuses audit trails."
  },
  organized_cluster: {
    title: "Organized Financial Cluster",
    description: "A coordinated group of accounts sharing common transaction endpoints, hardware/IP logins, or temporal execution spikes, signaling a professional money laundering network."
  }
}

function FinancialAlertCard({ alert }: { alert: SuspiciousTransactionAlert }) {
  const explanation = TYPOLOGY_EXPLANATIONS[alert.typology] || {
    title: alert.typology.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()),
    description: "Suspicious financial pattern detected by automated anomaly scanners."
  }

  // Helper to format evidence trail key names
  function formatKey(key: string): string {
    return key.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
  }

  // Helper to format evidence values dynamically
  function renderValue(key: string, value: unknown): React.ReactNode {
    const valStr = String(value)
    if (key.includes("amount") || key.includes("volume")) {
      const amt = Number(value)
      if (!isNaN(amt)) {
        return <span className="font-semibold text-zinc-900 dark:text-zinc-100">₹{amt.toLocaleString("en-IN")}</span>
      }
    }
    if (key.includes("transaction_ids") || key.includes("txns")) {
      const ids = valStr.split(",")
      return (
        <div className="flex flex-wrap gap-1 mt-1 max-h-[80px] overflow-y-auto pr-1">
          {ids.map((id, i) => (
            <code key={i} className="text-[10px] rounded bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 text-zinc-600 dark:text-zinc-400 font-mono shrink-0">
              {id.slice(0, 8)}...
            </code>
          ))}
        </div>
      )
    }
    return <span className="font-mono text-zinc-700 dark:text-zinc-350">{valStr}</span>
  }

  return (
    <div className="flat-surface space-y-4 rounded-lg p-5 border border-zinc-200 dark:border-zinc-800/80 shadow-xs">
      {/* Header section with Badge & Confidence */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <Badge variant="critical" className="px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase">
              {explanation.title}
            </Badge>
          </div>
          <p className="text-[11px] text-zinc-500 mt-1 dark:text-zinc-400 leading-normal">
            {explanation.description}
          </p>
        </div>

        <div className="flex items-center gap-1.5 shrink-0 bg-zinc-100 dark:bg-zinc-850 px-2 py-1 rounded-md">
          <span className="text-[11px] font-bold text-zinc-650 dark:text-zinc-300">
            {Math.round(alert.confidence * 100)}%
          </span>
          <span className="text-[9px] uppercase tracking-wider text-zinc-450 dark:text-zinc-500">Confidence</span>
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <button type="button" className="text-zinc-450 hover:text-zinc-600 dark:hover:text-zinc-300">
                  <Info className="w-3 h-3" />
                </button>
              </TooltipTrigger>
              <TooltipContent className="max-w-xs">
                <p className="text-xs">Dynamic anomaly match confidence scoring. High scores reflect strict alignment with typologies in historical cases.</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      {/* Visual Flow Trail of transaction accounts */}
      <FinancialFlowDiagram accountsInvolved={alert.accounts_involved} />

      {/* Structured Evidence Trail Details */}
      <div className="rounded-md border border-zinc-100 bg-zinc-50/20 dark:border-zinc-850 dark:bg-zinc-950/20 p-3">
        <h4 className="text-[10px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500 mb-2 flex items-center gap-1">
          <HelpCircle className="size-3 text-accent-500" />
          Flagged Indicators & Evidence
        </h4>
        <dl className="grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2 text-xs">
          {Object.entries(alert.evidence_trail).map(([key, value]) => (
            <div key={key} className="flex flex-col border-b border-zinc-100/50 pb-1.5 last:border-0 last:pb-0 dark:border-zinc-800/30">
              <dt className="text-[10px] text-zinc-400 uppercase tracking-wider font-semibold">
                {formatKey(key)}
              </dt>
              <dd className="mt-0.5 text-zinc-700 dark:text-zinc-300">
                {renderValue(key, value)}
              </dd>
            </div>
          ))}
        </dl>
      </div>

      {/* Recommendations & Action directives */}
      <div className="flex items-start gap-2 border-t border-zinc-100 pt-3 dark:border-zinc-800/60">
        <CheckCircle2 className="size-4 text-emerald-500 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <p className="text-xs font-semibold text-zinc-850 dark:text-zinc-200">
            {alert.recommended_action}
          </p>
          <p className="text-[10px] italic text-zinc-450 dark:text-zinc-550 leading-relaxed">
            {alert.disclaimer}
          </p>
        </div>
      </div>
    </div>
  )
}

export { FinancialAlertCard }
export type { SuspiciousTransactionAlert }
