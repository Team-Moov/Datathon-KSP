/**
 * Police deployment recommendation, rendered from
 * /socio/calculate-staffing/{district_id}.
 *
 * Extracted out of ChatWidgetRenderer so the same view backs both surfaces:
 * the assistant's police_staffing_recommendation widget and the Sociological
 * Insights page. It previously existed only inside the chat renderer, so the
 * capability was unreachable unless you thought to ask for it in words.
 */

export interface PoliceStaffingData {
  district_name: string
  calculated_at: string
  metrics: {
    unemployment_rate: string
    urbanization_pct: string
    composite_stress_index: string
    recorded_incident_count: number
  }
  recommendation: {
    total_recommended_officers: number
    base_force_scale: number
    stress_multiplier: number
    allocations: Record<string, number>
    recommended_patrol_vehicles: number
    deployment_strategy: string
  }
}

function PoliceStaffingCard({ data }: { data: PoliceStaffingData }) {
  const rec = data.recommendation
  return (
    <div className="space-y-3 p-1">
      <div className="grid grid-cols-3 gap-2">
        <div className="rounded-md bg-indigo-50 p-2.5 text-center dark:bg-indigo-950/30">
          <p className="text-lg font-bold text-indigo-700 dark:text-indigo-300">
            {rec.total_recommended_officers.toLocaleString()}
          </p>
          <p className="mt-0.5 text-[10px] text-indigo-600/70 dark:text-indigo-400/70">Recommended Officers</p>
        </div>
        <div className="rounded-md bg-emerald-50 p-2.5 text-center dark:bg-emerald-950/30">
          <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">
            {rec.recommended_patrol_vehicles}
          </p>
          <p className="mt-0.5 text-[10px] text-emerald-600/70 dark:text-emerald-400/70">Patrol Vehicles</p>
        </div>
        <div className="rounded-md bg-amber-50 p-2.5 text-center dark:bg-amber-950/30">
          <p className="text-lg font-bold text-amber-700 dark:text-amber-300">×{rec.stress_multiplier}</p>
          <p className="mt-0.5 text-[10px] text-amber-600/70 dark:text-amber-400/70">Stress Multiplier</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-x-3 gap-y-1 px-1 text-[10px] text-zinc-500 dark:text-zinc-400">
        <span>
          Unemployment: <strong className="text-zinc-700 dark:text-zinc-300">{data.metrics.unemployment_rate}</strong>
        </span>
        <span>
          Urbanization: <strong className="text-zinc-700 dark:text-zinc-300">{data.metrics.urbanization_pct}</strong>
        </span>
        <span>
          Stress Index:{" "}
          <strong className="text-zinc-700 dark:text-zinc-300">{data.metrics.composite_stress_index}</strong>
        </span>
        <span>
          Incidents in DB:{" "}
          <strong className="text-zinc-700 dark:text-zinc-300">{data.metrics.recorded_incident_count}</strong>
        </span>
      </div>

      <div className="space-y-1.5 px-1">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
          Allocation Breakdown
        </p>
        {Object.entries(rec.allocations).map(([role, count]) => {
          const pct =
            rec.total_recommended_officers > 0 ? Math.round((count / rec.total_recommended_officers) * 100) : 0
          return (
            <div key={role} className="space-y-0.5">
              <div className="flex justify-between text-[10px]">
                <span className="text-zinc-600 dark:text-zinc-300">{role}</span>
                <span className="font-mono text-zinc-800 dark:text-zinc-200">
                  {count.toLocaleString()} ({pct}%)
                </span>
              </div>
              <div className="h-1 rounded-full bg-zinc-200 dark:bg-zinc-800">
                <div className="h-1 rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
              </div>
            </div>
          )
        })}
      </div>

      <p className="px-1 text-[10px] italic leading-relaxed text-zinc-500 dark:text-zinc-400">
        {rec.deployment_strategy}
      </p>
      <p className="px-1 text-[9px] text-zinc-400 dark:text-zinc-600">
        Calculated {data.calculated_at} · Model: stress-weighted base-force scale
      </p>
    </div>
  )
}

export { PoliceStaffingCard }
