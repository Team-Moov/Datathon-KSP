import * as React from "react"
import { CheckCircle2, Info } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { SocioCorrelationResponse } from "@/features/socio/socioApi"

interface SocioCorrelationMatrixProps {
  data: SocioCorrelationResponse
}

export function SocioCorrelationMatrix({ data }: SocioCorrelationMatrixProps) {
  const [showChiOnly, setShowChiOnly] = React.useState(false)

  return (
    <div className="space-y-4">
      <Card className="border-indigo-100 dark:border-indigo-950/50 bg-gradient-to-br from-white to-indigo-50/20 dark:from-zinc-900 dark:to-indigo-950/10 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
                <span>Statistical Correlation Matrix</span>
                <span className="text-xs font-normal px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950/80 dark:text-indigo-300">
                  N = {data.sample_size} District-Years
                </span>
              </CardTitle>
              <CardDescription className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
                Empirical Pearson correlation ($r$) comparing socio-disorganization factors against Crime Harm Index (CHI) vs. Raw Counts.
              </CardDescription>
            </div>
            <button
              onClick={() => setShowChiOnly(!showChiOnly)}
              className="text-xs px-3 py-1.5 rounded-md font-medium transition-colors bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300"
            >
              {showChiOnly ? "Show Comparison Table" : "Highlight CHI Harm"}
            </button>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          <div className="overflow-x-auto rounded-lg border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 dark:bg-zinc-800/60 text-zinc-600 dark:text-zinc-400 uppercase tracking-wider">
                <tr>
                  <th className="py-2.5 px-3 font-semibold">Socio-Economic Indicator</th>
                  {!showChiOnly && <th className="py-2.5 px-3 font-semibold text-center">{"Raw Count ($r_{raw}$)"}</th>}
                  <th className="py-2.5 px-3 font-semibold text-center text-indigo-600 dark:text-indigo-400">{"CHI Harm ($r_{CHI}$)"}</th>
                  <th className="py-2.5 px-3 font-semibold text-center">{"Significance ($p$-val)"}</th>
                  {!showChiOnly && <th className="py-2.5 px-3 font-semibold text-right">Harm Alignment</th>}
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
                      <td className="py-3 px-3 text-center font-semibold text-indigo-600 dark:text-indigo-400 bg-indigo-50/30 dark:bg-indigo-950/20">
                        {item.r_chi.toFixed(2)}
                      </td>
                      <td className="py-3 px-3 text-center">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                          {item.significance} (p={item.p_val_chi})
                        </span>
                      </td>
                      {!showChiOnly && (
                        <td className="py-3 px-3 text-right font-medium">
                          <span className={isPositiveDelta ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}>
                            {isPositiveDelta ? `+${delta.toFixed(2)} Harm Delta` : `${delta.toFixed(2)} Harm Delta`}
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
            <div className="p-3 rounded-lg bg-indigo-50/50 dark:bg-indigo-950/30 border border-indigo-100 dark:border-indigo-900/40 flex items-start gap-2.5">
              <CheckCircle2 className="w-4 h-4 text-indigo-600 dark:text-indigo-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-semibold text-indigo-900 dark:text-indigo-200">CHI Harm Impact Finding</div>
                <p className="text-[11px] text-indigo-700 dark:text-indigo-300/80 mt-0.5">
                  {data.chi_vs_raw_delta}
                </p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-amber-50/50 dark:bg-amber-950/30 border border-amber-100 dark:border-amber-900/40 flex items-start gap-2.5">
              <Info className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
              <div>
                <div className="text-xs font-semibold text-amber-900 dark:text-amber-200">Policy Takeaway</div>
                <p className="text-[11px] text-amber-700 dark:text-amber-300/80 mt-0.5">
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
