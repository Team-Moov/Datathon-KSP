import { AlertTriangle, BookOpen, CheckCircle, Sparkles } from "lucide-react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import type { PolicyRecommendationsResponse } from "@/features/socio/socioApi"

interface PolicyRecommendationsCardProps {
  data: PolicyRecommendationsResponse
}

export function PolicyRecommendationsCard({ data }: PolicyRecommendationsCardProps) {
  return (
    <div className="space-y-4">
      <Card className="border-indigo-200 dark:border-indigo-900/60 bg-gradient-to-br from-indigo-50/30 via-white to-purple-50/20 dark:from-indigo-950/20 dark:via-zinc-900 dark:to-purple-950/20 shadow-sm">
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-50">
                <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
                <span>Criminological Policy Diagnostic — {data.district_name}</span>
              </CardTitle>
              <CardDescription className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                Automated preventive interventions grounded in criminological theory and district socio-economic risk factors.
              </CardDescription>
            </div>
            <span
              className={`text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wider ${
                data.stress_index > 0.65
                  ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                  : data.stress_index > 0.45
                  ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300"
                  : "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
              }`}
            >
              {data.risk_level}
            </span>
          </div>
        </CardHeader>

        <CardContent className="space-y-4">
          {/* Summary Chips */}
          <div className="grid grid-cols-3 gap-3 p-3 rounded-lg bg-zinc-100/60 dark:bg-zinc-800/50 text-xs">
            <div>
              <span className="text-[11px] text-zinc-500">Unemployment Rate</span>
              <div className="font-bold text-zinc-800 dark:text-zinc-200">{data.indicators_summary.unemployment_rate}</div>
            </div>
            <div>
              <span className="text-[11px] text-zinc-500">Urbanization Level</span>
              <div className="font-bold text-zinc-800 dark:text-zinc-200">{data.indicators_summary.urbanization_pct}</div>
            </div>
            <div>
              <span className="text-[11px] text-zinc-500">Literacy Rate</span>
              <div className="font-bold text-zinc-800 dark:text-zinc-200">{data.indicators_summary.literacy_rate}</div>
            </div>
          </div>

          {/* Action Recommendations List */}
          <div className="space-y-3">
            <h4 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200 uppercase tracking-wider">
              Targeted Preventive Action Items
            </h4>
            {data.recommendations.map((rec, idx) => (
              <div
                key={idx}
                className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 space-y-2"
              >
                <div className="flex justify-between items-center">
                  <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400">{rec.domain}</span>
                  <span
                    className={`text-[10px] px-2 py-0.5 rounded font-bold uppercase ${
                      rec.priority === "High"
                        ? "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                        : "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                    }`}
                  >
                    {rec.priority} Priority
                  </span>
                </div>

                <div className="flex items-start gap-2">
                  <BookOpen className="w-3.5 h-3.5 text-zinc-400 shrink-0 mt-0.5" />
                  <span className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                    Grounding: {rec.theory_grounding}
                  </span>
                </div>

                <p className="text-xs text-zinc-800 dark:text-zinc-200 leading-relaxed font-normal">
                  {rec.action}
                </p>

                <div className="flex items-center gap-1.5 text-[11px] text-emerald-600 dark:text-emerald-400 font-medium pt-1">
                  <CheckCircle className="w-3 h-3 shrink-0" />
                  <span>Expected Impact: {rec.expected_impact}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Criminological Guardrail Note */}
          <div className="p-3 rounded-lg bg-zinc-100 dark:bg-zinc-800/60 text-[11px] text-zinc-600 dark:text-zinc-400 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" />
            <span>{data.criminological_note}</span>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
