import { Building2, TrendingUp } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { UrbanizationImpactItem } from "@/features/socio/socioApi"

interface UrbanizationImpactChartProps {
  data: UrbanizationImpactItem[]
}

export function UrbanizationImpactChart({ data }: UrbanizationImpactChartProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <Card className="border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
            <Building2 className="w-4 h-4 text-accent-600 dark:text-accent-400" />
            <span>{t("urbanizationChart.title")}</span>
          </CardTitle>
          <CardDescription className="text-xs text-zinc-500 dark:text-zinc-400">
            {t("urbanizationChart.description")}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.map((item, idx) => (
              <div
                key={idx}
                className="p-4 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-gradient-to-br from-white to-zinc-50/50 dark:from-zinc-900 dark:to-zinc-800/40 shadow-sm space-y-3"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h4 className="text-sm font-bold text-zinc-900 dark:text-zinc-50">{item.district_name}</h4>
                    <span className="text-xs text-zinc-500 font-medium">{item.phase}</span>
                  </div>
                  <span className="text-xs px-2.5 py-1 rounded-full font-semibold bg-accent-500/15 text-accent-700 dark:text-accent-300">
                    {item.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-2 p-2.5 rounded-lg bg-zinc-100/70 dark:bg-zinc-800/70 text-xs">
                  <div>
                    <span className="text-[11px] text-zinc-500">{t("urbanizationChart.urbanGrowth")}</span>
                    <div className="font-bold text-accent-600 dark:text-accent-400">+{item.urbanization_growth_pct}%</div>
                  </div>
                  <div>
                    <span className="text-[11px] text-zinc-500">{t("urbanizationChart.crimeVelocityShift")}</span>
                    <div className="font-bold text-caution-600 dark:text-caution-500">{item.crime_velocity_change}</div>
                  </div>
                </div>

                <div className="space-y-1 text-xs">
                  <div className="flex items-center gap-1.5 text-zinc-700 dark:text-zinc-300 font-medium">
                    <TrendingUp className="w-3.5 h-3.5 text-accent-500" />
                    <span>{t("urbanizationChart.primarySurge")}: {item.primary_crime_head}</span>
                  </div>
                  <p className="text-[11px] text-zinc-500 dark:text-zinc-400 leading-relaxed italic">
                    {t("urbanizationChart.mechanism")}: "{item.social_mechanism}"
                  </p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
