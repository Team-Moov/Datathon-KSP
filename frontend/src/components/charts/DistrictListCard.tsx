import { useTranslation } from "react-i18next"

import type { DistrictOption } from "@/features/socio/socioApi"

/** Districts the assistant can resolve a district_id from — mirrors the socio
 * page's district selector so chat and the dashboard show the same values. */
function DistrictListCard({ districts }: { districts: DistrictOption[] }) {
  const { t } = useTranslation()
  if (districts.length === 0) {
    return <p className="px-1 text-xs text-zinc-400">{t("districtList.noDistrictsFound")}</p>
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
              {d.unemployment_rate !== null ? t("districtList.unemployment", { pct: d.unemployment_rate.toFixed(1) }) : t("districtList.noIndicatorData")}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-accent-500/10 px-2 py-0.5 text-[10px] font-medium text-accent-600 dark:text-accent-400">
            {d.composite_stress_index !== null ? t("districtList.stress", { value: d.composite_stress_index.toFixed(2) }) : t("common.noData")}
          </span>
        </li>
      ))}
    </ul>
  )
}

export { DistrictListCard }
