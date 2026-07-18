import { ArrowRight } from "lucide-react"

function truncateAccountLabel(account: string): string {
  return account.length > 18 ? `${account.slice(0, 8)}...${account.slice(-4)}` : account
}

/**
 * Renders the accounts_involved chain from a structuring/funnel/layering alert
 * as a left-to-right flow — these typologies are shapes in the transaction
 * graph (fan-out, fan-in-then-out, cycle), so a chain of arrows communicates
 * the pattern more directly than a bar chart would.
 */
function FinancialFlowDiagram({ accountsInvolved }: { accountsInvolved: string[] }) {
  if (accountsInvolved.length === 0) return null

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {accountsInvolved.map((account, index) => (
        <div key={`${account}-${index}`} className="flex items-center gap-1.5">
          <span className="flat-surface rounded-md px-2.5 py-1 font-mono text-[11px] text-zinc-700 dark:text-zinc-200">
            {truncateAccountLabel(account)}
          </span>
          {index < accountsInvolved.length - 1 ? <ArrowRight className="size-3.5 shrink-0 text-zinc-300 dark:text-zinc-600" /> : null}
        </div>
      ))}
    </div>
  )
}

export { FinancialFlowDiagram }
