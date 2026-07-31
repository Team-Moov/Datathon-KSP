import type { PersonAccount } from "@/features/financial/financialApi"

/** Accounts linked to a person's transactions — the entry point for the financial
 * workflow from chat: pick one of these, then hand it to a structuring/funnel/scan tool. */
function FinancialAccountsList({ accounts }: { accounts: PersonAccount[] }) {
  if (accounts.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No financial transactions linked to this person.</p>
  }
  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {accounts.map((acct) => (
        <li key={acct.account} className="flex items-center justify-between px-3 py-2 text-xs">
          <div>
            <p className="font-mono font-medium text-zinc-800 dark:text-zinc-100">{acct.account}</p>
            <p className="text-[10px] text-zinc-400">{acct.txn_count} transaction{acct.txn_count === 1 ? "" : "s"}</p>
          </div>
          {acct.flagged ? (
            <span className="shrink-0 rounded-full bg-critical-500/10 px-2 py-0.5 text-[10px] font-medium text-critical-600 dark:text-critical-400">
              Flagged
            </span>
          ) : null}
        </li>
      ))}
    </ul>
  )
}

export { FinancialAccountsList }
