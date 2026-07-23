import { ResponsiveContainer, Sankey, Tooltip } from "recharts"

function truncateAccountLabel(account: string): string {
  return account.length > 18 ? `${account.slice(0, 8)}...${account.slice(-4)}` : account
}

// recharts doesn't publicly export its Sankey NodeProps type from the package
// root (only from an internal module path), so this covers just the fields
// this component actually reads off the node-render callback.
interface SankeyNodeRenderProps {
  x: number
  y: number
  width: number
  height: number
  payload: { name: string }
}

function AccountNode({ x, y, width, height, payload }: SankeyNodeRenderProps) {
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={2} className="fill-accent-500 dark:fill-accent-400" fillOpacity={0.85} />
      <text
        x={x + width / 2}
        y={y - 6}
        textAnchor="middle"
        fontSize={10}
        fontFamily="ui-monospace, monospace"
        className="fill-zinc-600 dark:fill-zinc-300"
      >
        {payload.name}
      </text>
    </g>
  )
}

/**
 * Renders the accounts_involved chain from a structuring/funnel/layering alert
 * as an actual Sankey flow — these typologies are shapes in the transaction
 * graph (fan-out, fan-in-then-out, cycle), so a directional flow diagram
 * communicates the pattern more directly than a static chip chain did.
 *
 * Consecutive hops are drawn as equal-weight links, not amount-weighted: the
 * alert object (`evidence_trail`) only ever carries an aggregate total for
 * the whole pattern (e.g. structuring's `total_amount`), never a real
 * per-hop transaction amount to encode into link width without fabricating one.
 */
function FinancialFlowDiagram({ accountsInvolved }: { accountsInvolved: string[] }) {
  if (accountsInvolved.length === 0) return null

  if (accountsInvolved.length === 1) {
    return (
      <span className="flat-surface inline-block rounded-md px-2.5 py-1 font-mono text-[11px] text-zinc-700 dark:text-zinc-200">
        {truncateAccountLabel(accountsInvolved[0])}
      </span>
    )
  }

  const nodes = accountsInvolved.map((account) => ({ name: truncateAccountLabel(account) }))
  const links = accountsInvolved.slice(0, -1).map((_, index) => ({ source: index, target: index + 1, value: 1 }))

  return (
    <div className="h-[140px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <Sankey
          data={{ nodes, links }}
          nodePadding={20}
          nodeWidth={8}
          linkCurvature={0.5}
          node={AccountNode}
          link={{ stroke: "currentColor", strokeOpacity: 0.25 }}
          margin={{ top: 16, right: 16, bottom: 8, left: 16 }}
          className="text-accent-500"
        >
          <Tooltip />
        </Sankey>
      </ResponsiveContainer>
    </div>
  )
}

export { FinancialFlowDiagram }
