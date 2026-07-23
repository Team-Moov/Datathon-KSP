interface GwrRun {
  model_version: string
  run_timestamp: string
  data_version: string
  gwr_coefficients: Record<string, number>
  composite_score: number | null
}

/** Latest-first list of GWR runs for one district — each run's coefficients
 * show how strongly each socio-economic factor locally predicts CHI-weighted
 * crime harm there (§6.2). Versioned, never overwritten, so this can show a
 * trend across runs, not just the latest one. */
function GwrCoefficientsList({ runs }: { runs: GwrRun[] }) {
  if (runs.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No GWR runs yet for this district.</p>
  }
  return (
    <ul className="space-y-2">
      {runs.map((run, index) => (
        <li key={`${run.model_version}-${run.run_timestamp}-${index}`} className="rounded-md border border-zinc-200 p-2.5 text-xs dark:border-zinc-800">
          <div className="mb-1.5 flex items-center justify-between text-[10px] text-zinc-400">
            <span>{run.model_version} · {run.data_version}</span>
            <span>{new Date(run.run_timestamp).toLocaleDateString()}</span>
          </div>
          <dl className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            {Object.entries(run.gwr_coefficients).map(([factor, value]) => (
              <div key={factor}>
                <dt className="text-[10px] text-zinc-400">{factor.replace(/_/g, " ")}</dt>
                <dd className={value >= 0 ? "font-medium text-critical-600 dark:text-critical-400" : "font-medium text-accent-600 dark:text-accent-400"}>
                  {value >= 0 ? "+" : ""}
                  {value.toFixed(3)}
                </dd>
              </div>
            ))}
          </dl>
        </li>
      ))}
    </ul>
  )
}

export { GwrCoefficientsList }
export type { GwrRun }
