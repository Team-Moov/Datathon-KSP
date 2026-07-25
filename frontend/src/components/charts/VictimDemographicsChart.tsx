import { ShieldCheck, Users } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { VictimDemographicsData } from "@/features/socio/socioApi"

interface VictimDemographicsChartProps {
  data: VictimDemographicsData
}

export function VictimDemographicsChart({ data }: VictimDemographicsChartProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <Card className="border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
            <Users className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span>{t("victimDemographics.title")}</span>
          </CardTitle>
          <CardDescription className="text-xs text-zinc-500 dark:text-zinc-400">
            {t("victimDemographics.description")}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Age Group Breakdown */}
          <div>
            <h4 className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 uppercase tracking-wider mb-3">
              {t("victimDemographics.ageCohortExposure")}
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
              {data.age_groups.map((group, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg border border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/40 space-y-2"
                >
                  <div className="flex justify-between items-center">
                    <span className="text-xs font-bold text-zinc-900 dark:text-zinc-100">{group.cohort}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 font-semibold">
                      {t("victimDemographics.share", { pct: group.overall_pct })}
                    </span>
                  </div>
                  <div className="space-y-1.5 text-[11px]">
                    <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                      <span>{t("victimDemographics.cyberCrime")}:</span>
                      <span className="font-semibold text-zinc-800 dark:text-zinc-200">{group.cyber_pct}%</span>
                    </div>
                    <div className="w-full bg-zinc-200 dark:bg-zinc-700 h-1 rounded-full overflow-hidden">
                      <div className="bg-indigo-500 h-full" style={{ width: `${group.cyber_pct}%` }} />
                    </div>

                    <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                      <span>{t("victimDemographics.propertyTheft")}:</span>
                      <span className="font-semibold text-zinc-800 dark:text-zinc-200">{group.theft_pct}%</span>
                    </div>
                    <div className="w-full bg-zinc-200 dark:bg-zinc-700 h-1 rounded-full overflow-hidden">
                      <div className="bg-emerald-500 h-full" style={{ width: `${group.theft_pct}%` }} />
                    </div>

                    <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
                      <span>{t("victimDemographics.crimesAgainstPerson")}:</span>
                      <span className="font-semibold text-zinc-800 dark:text-zinc-200">{group.violent_pct}%</span>
                    </div>
                    <div className="w-full bg-zinc-200 dark:bg-zinc-700 h-1 rounded-full overflow-hidden">
                      <div className="bg-rose-500 h-full" style={{ width: `${group.violent_pct}%` }} />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Gender & Vulnerability Distribution */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
            <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-3">
              <h4 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 uppercase tracking-wider">
                {t("victimDemographics.genderVictimizationSplit")}
              </h4>
              <div className="space-y-2.5">
                {data.gender_distribution.map((item, idx) => (
                  <div key={idx} className="space-y-1">
                    <div className="flex justify-between text-xs font-medium text-zinc-700 dark:text-zinc-300">
                      <span>{item.category}</span>
                      <span className="text-[11px] text-zinc-500">
                        {t("victimDemographics.maleFemaleSplit", { male: item.male_pct, female: item.female_pct })}
                      </span>
                    </div>
                    <div className="flex h-2 w-full rounded-full overflow-hidden bg-zinc-100 dark:bg-zinc-800">
                      <div className="bg-blue-500 h-full" style={{ width: `${item.male_pct}%` }} title={t("victimDemographics.male")} />
                      <div className="bg-purple-500 h-full" style={{ width: `${item.female_pct}%` }} title={t("victimDemographics.female")} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-3">
              <h4 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 uppercase tracking-wider">
                {t("victimDemographics.socioEconomicStratumVulnerability")}
              </h4>
              <div className="space-y-2 text-xs">
                {data.socio_economic_vulnerability.map((item, idx) => (
                  <div key={idx} className="p-2 rounded bg-zinc-50 dark:bg-zinc-800/50 flex items-center justify-between">
                    <div>
                      <div className="font-semibold text-zinc-900 dark:text-zinc-100">{item.stratum}</div>
                      <div className="text-[11px] text-zinc-500 dark:text-zinc-400">{t("victimDemographics.risk")}: {item.primary_risk}</div>
                    </div>
                    <div className="text-right">
                      <span className="inline-block px-2 py-0.5 text-[11px] font-bold rounded bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">
                        {t("victimDemographics.score")}: {item.vulnerability_score.toFixed(2)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Resource Allocation Recommendation */}
          <div className="p-3 rounded-lg bg-emerald-50/50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/30 flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
            <div>
              <div className="text-xs font-semibold text-emerald-900 dark:text-emerald-200">{t("victimDemographics.resourceAllocationDirective")}</div>
              <p className="text-[11px] text-emerald-700 dark:text-emerald-300/80 mt-0.5">
                {data.police_resource_recommendation}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
