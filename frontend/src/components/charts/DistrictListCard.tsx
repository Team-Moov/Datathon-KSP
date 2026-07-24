import type { DistrictOption } from "@/features/socio/socioApi"

/** Districts the assistant can resolve a district_id from — mirrors the socio
 * page's district selector so chat and the dashboard show the same values. */
function DistrictListCard({ districts }: { districts: DistrictOption[] }) {
  if (districts.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">No districts found.</p>
  }
  return (
    <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
      {districts.map((d) => (
        <li key={d.district_id} className="flex items-center justify-between px-3 py-2 text-xs">
          <div>
            <p className="font-medium text-zinc-800 dark:text-zinc-100">
              {d.name} <span className="text-zinc-400 font-normal">({d.code})</span>
            </p>
            <p className="text-[10px] text-zinc-400">
              {d.unemployment_rate !== null ? `Unemployment ${d.unemployment_rate.toFixed(1)}%` : "No indicator data"}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] font-medium text-indigo-600 dark:text-indigo-400">
            {d.composite_stress_index !== null ? `Stress ${d.composite_stress_index.toFixed(2)}` : "No data"}
          </span>
        </li>
      ))}
    </ul>
  )
}

export { DistrictListCard }
