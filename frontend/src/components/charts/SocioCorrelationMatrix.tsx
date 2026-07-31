import * as React from "react"
import { CheckCircle2, Info } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { SocioCorrelationResponse } from "@/features/socio/socioApi"

interface SocioCorrelationMatrixProps {
  data: SocioCorrelationResponse
}

export function SocioCorrelationMatrix({ data }: SocioCorrelationMatrixProps) {
  const { t } = useTranslation()
  const [showChiOnly, setShowChiOnly] = React.useState(false)

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
                <span>{t("socioCorrelation.statisticalCorrelationMatrix")}</span>
                <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-accent-500/15 text-accent-700 dark:text-accent-300">
                  {t("socioCorrelation.sampleSize", { count: data.sample_size })}
                </span>
              </CardTitle>
              <CardDescription className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                {t("socioCorrelation.description")}
              </CardDescription>
            </div>
            <button
              onClick={() => setShowChiOnly(!showChiOnly)}
              className="text-xs px-3 py-1.5 rounded-md font-medium transition-colors bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300"
            >
              {showChiOnly ? t("socioCorrelation.showComparisonTable") : t("socioCorrelation.highlightChiHarm")}
            </button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 dark:bg-zinc-800/60 text-zinc-600 dark:text-zinc-400 uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3 font-semibold">{t("socioCorrelation.socioEconomicIndicator")}</th>
                  {!showChiOnly && <th className="py-2.5 px-3 font-semibold text-center">{"Raw Count ($r_{raw}$)"}</th>}
                  <th className="py-2.5 px-3 font-semibold text-center text-accent-600 dark:text-accent-400">{"CHI Harm ($r_{CHI}$)"}</th>
                  <th className="py-2.5 px-3 font-semibold text-center">{"Significance ($p$-val)"}</th>
                  {!showChiOnly && <th className="py-2.5 px-3 font-semibold text-right">{t("socioCorrelation.harmAlignment")}</th>}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-200 dark:divide-zinc-800 bg-white dark:bg-zinc-900">
                {data.correlations.map((item, idx) => {
                  const delta = item.r_chi - item.r_raw
                  const isPositiveDelta = delta > 0
                  return (
                    <tr key={idx} className="hover:bg-zinc-50/50 dark:hover:bg-zinc-800/30 transition-colors">
                      <td className="py-3 px-3 font-medium text-zinc-900 dark:text-zinc-100">
                        {item.indicator}
                      </td>
                      {!showChiOnly && (
                        <td className="py-3 px-3 text-center text-zinc-600 dark:text-zinc-400">
                          {item.r_raw.toFixed(2)}
                        </td>
                      )}
                      <td className="py-3 px-3 text-center font-semibold text-accent-600 dark:text-accent-400 bg-accent-500/5">
                        {item.r_chi.toFixed(2)}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-affirm-500/15 text-affirm-600 dark:text-affirm-500">
                          {item.significance} (p={item.p_val_chi})
                        </span>
                      </td>
                      {!showChiOnly && (
                        <td className="py-3 px-3 text-right font-medium">
                          <span className={isPositiveDelta ? "text-affirm-600 dark:text-affirm-500" : "text-caution-600 dark:text-caution-500"}>
                            {isPositiveDelta ? `+${delta.toFixed(2)}` : delta.toFixed(2)} {t("socioCorrelation.harmDelta")}
                          </span>
                        </td>
                      )}
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
            <div className="p-3 rounded-lg bg-accent-500/5 border border-accent-500/20 flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-accent-600 dark:text-accent-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-semibold text-accent-800 dark:text-accent-200">{t("socioCorrelation.chiHarmImpactFinding")}</div>
                <p className="text-[11px] text-accent-700 dark:text-accent-300/80 mt-0.5">
                  {data.chi_vs_raw_delta}
                </p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-caution-500/5 border border-caution-500/20 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-caution-600 dark:text-caution-500 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-semibold text-caution-700 dark:text-caution-500">{t("socioCorrelation.policyTakeaway")}</div>
                <p className="text-[11px] text-caution-700/80 dark:text-caution-500/80 mt-0.5">
                  {data.key_takeaway}
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
