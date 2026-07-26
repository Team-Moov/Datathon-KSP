import * as React from "react"
import { ArrowRight, Copy, Check, Repeat, Landmark, ArrowRightLeft } from "lucide-react"

function truncateAccountLabel(account: string): string {
  return account.length > 18 ? `${account.slice(0, 8)}...${account.slice(-4)}` : account
}

function FinancialFlowDiagram({ accountsInvolved }: { accountsInvolved: string[] }) {
  const [copiedIndex, setCopiedIndex] = React.useState<number | null>(null)

  if (accountsInvolved.length === 0) return null

  // Check if it's a closed loop (laundering cycle)
  const isCycle = 
    accountsInvolved.length > 2 && 
    accountsInvolved[0] === accountsInvolved[accountsInvolved.length - 1]

  function copyToClipboard(text: string, index: number) {
    void navigator.clipboard.writeText(text)
    setCopiedIndex(index)
    setTimeout(() => setCopiedIndex(null), 1500)
  }

  return (
    <div className="w-full py-4 px-2 rounded-lg border border-zinc-200/50 bg-zinc-50/50 dark:border-zinc-800/40 dark:bg-zinc-950/20">
      <div className="mb-2 flex items-center justify-between px-1 text-[10px] uppercase font-bold tracking-wider text-zinc-400 dark:text-zinc-500">
        <div className="flex items-center gap-1.5">
          <ArrowRightLeft className="size-3 text-accent-500" />
          <span>Visual Flow Trail</span>
        </div>
        {isCycle && (
          <span className="flex items-center gap-1 text-rose-500 dark:text-rose-400 font-semibold animate-pulse">
            <Repeat className="size-3" />
            Layering Cycle Detected
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-y-3 gap-x-2 py-1">
        {accountsInvolved.map((account, idx) => {
          const isStart = idx === 0
          const isEnd = idx === accountsInvolved.length - 1
          const isIntermediateLoopNode = isEnd && isCycle

          // Visual styles based on position
          let borderStyle = "border-zinc-200 dark:border-zinc-800"
          let bgStyle = "bg-white dark:bg-zinc-900"
          let textStyle = "text-zinc-700 dark:text-zinc-300"
          let roleLabel = `Hop #${idx + 1}`

          if (isStart) {
            borderStyle = "border-indigo-200 dark:border-indigo-900/50"
            bgStyle = "bg-indigo-50/50 dark:bg-indigo-950/30"
            textStyle = "text-indigo-800 dark:text-indigo-300"
            roleLabel = "Origin Node"
          } else if (isIntermediateLoopNode) {
            borderStyle = "border-rose-300 dark:border-rose-900/60"
            bgStyle = "bg-rose-50/50 dark:bg-rose-950/30"
            textStyle = "text-rose-800 dark:text-rose-300 font-bold"
            roleLabel = "Cycle Return"
          } else if (isEnd) {
            borderStyle = "border-emerald-200 dark:border-emerald-900/50"
            bgStyle = "bg-emerald-50/50 dark:bg-emerald-950/30"
            textStyle = "text-emerald-800 dark:text-emerald-300"
            roleLabel = "Target End Node"
          }

          return (
            <React.Fragment key={idx}>
              {/* Node Card */}
              <div 
                className={`relative flex items-center gap-2 rounded-md border ${borderStyle} ${bgStyle} px-3 py-1.5 shadow-xs transition-all hover:scale-[1.02]`}
                title={account}
              >
                <div className="flex flex-col text-left">
                  <span className="text-[8px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                    {roleLabel}
                  </span>
                  <div className="flex items-center gap-1.5">
                    <Landmark className="size-3 text-zinc-450 dark:text-zinc-500 shrink-0" />
                    <span className={`font-mono text-xs font-semibold ${textStyle}`}>
                      {truncateAccountLabel(account)}
                    </span>
                  </div>
                </div>

                <button 
                  type="button"
                  onClick={() => copyToClipboard(account, idx)}
                  className="ml-1 rounded p-1 text-zinc-450 hover:bg-zinc-100 hover:text-zinc-700 dark:text-zinc-500 dark:hover:bg-zinc-800 dark:hover:text-zinc-300 transition"
                  title="Copy account number"
                >
                  {copiedIndex === idx ? (
                    <Check className="size-3 text-emerald-500" />
                  ) : (
                    <Copy className="size-3" />
                  )}
                </button>
              </div>

              {/* Edge Arrow */}
              {!isEnd && (
                <div className="flex items-center justify-center text-zinc-300 dark:text-zinc-700 mx-0.5 animate-pulse">
                  <ArrowRight className="size-3.5" />
                </div>
              )}
            </React.Fragment>
          )
        })}
      </div>

      {isCycle && (
        <div className="mt-3 flex items-start gap-1.5 rounded-md border border-rose-100 bg-rose-50/30 p-2 text-[10px] text-rose-600 dark:border-rose-950/20 dark:bg-rose-950/10 dark:text-rose-400 leading-normal">
          <InfoIcon className="mt-0.5 size-3 shrink-0" />
          <span>
            <strong>Loop Indicator:</strong> Hop #{accountsInvolved.length} links back to origin account (Hop #1), indicating a closed laundering cycle. The origin node and destination node are the exact same bank node, masking the flow of resources.
          </span>
        </div>
      )}
    </div>
  )
}

function InfoIcon({ className }: { className?: string }) {
  return (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2.5" 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      className={className}
    >
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" />
      <path d="M12 8h.01" />
    </svg>
  )
}

export { FinancialFlowDiagram }
