import * as React from "react"
import { useMutation } from "@tanstack/react-query"
import axios from "axios"
import { Sparkles, WifiOff } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import type { ApiErrorPayload } from "@/lib/types/api"
import { generateCaseBrief } from "../casesApi"

interface CaseBriefResult {
  context_summary?: string
  leads?: { type: string; name?: string; person_id?: string; source_tool?: string; confidence?: number }[]
  similar_cases?: { case_id: string; crime_no: string; disposition: string | null }[]
  disclaimer?: string
}

function AiBriefPanel({ caseId }: { caseId: string }) {
  const [isAiUnavailable, setIsAiUnavailable] = React.useState(false)

  const briefMutation = useMutation({
    mutationFn: () => generateCaseBrief(caseId) as Promise<CaseBriefResult>,
    onMutate: () => setIsAiUnavailable(false),
    onError: (error) => {
      const isAiOutage =
        axios.isAxiosError<ApiErrorPayload>(error) &&
        error.response?.status === 503 &&
        error.response.data?.error === "ai_unavailable"
      setIsAiUnavailable(isAiOutage)
    },
  })

  const brief = briefMutation.data

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between">
        <CardTitle>Investigator Brief</CardTitle>
        <Button size="sm" variant="outline" className="gap-1.5" onClick={() => briefMutation.mutate()} disabled={briefMutation.isPending}>
          <Sparkles className="size-3.5" />
          {briefMutation.isPending ? "Generating..." : "Generate"}
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {isAiUnavailable ? (
          <div className="flex items-start gap-2 rounded-md border border-caution-500/40 bg-caution-500/10 p-3 text-xs text-caution-600 dark:text-caution-500">
            <WifiOff className="mt-0.5 size-3.5 shrink-0" />
            <span>
              AI narration is temporarily unavailable. The deterministic analytical tools this brief relies on are
              still working — try again shortly.
            </span>
          </div>
        ) : briefMutation.isError ? (
          <p className="text-xs text-critical-500">{extractApiErrorMessage(briefMutation.error)}</p>
        ) : null}

        {!brief && !briefMutation.isPending && !briefMutation.isError ? (
          <p className="text-xs text-zinc-400 dark:text-zinc-600">
            Generates a timeline summary, similar-case comparisons, and deterministic leads for this case.
          </p>
        ) : null}

        {brief ? (
          <div className="space-y-3">
            {brief.context_summary ? <p className="text-sm text-zinc-700 dark:text-zinc-200">{brief.context_summary}</p> : null}

            {brief.leads && brief.leads.length > 0 ? (
              <div>
                <p className="section-label mb-1">Leads</p>
                <ul className="space-y-1">
                  {brief.leads.map((lead, index) => (
                    <li key={index} className="text-xs text-zinc-600 dark:text-zinc-300">
                      {lead.name ?? lead.person_id} — {lead.type} (source: {lead.source_tool}, confidence{" "}
                      {typeof lead.confidence === "number" ? Math.round(lead.confidence * 100) : "—"}%)
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {brief.similar_cases && brief.similar_cases.length > 0 ? (
              <div>
                <p className="section-label mb-1">Similar Cases</p>
                <ul className="space-y-1">
                  {brief.similar_cases.map((similar) => (
                    <li key={similar.case_id} className="font-mono text-xs text-zinc-600 dark:text-zinc-300">
                      {similar.crime_no} — {similar.disposition ?? "status unknown"}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {brief.disclaimer ? <p className="text-[11px] italic text-zinc-400 dark:text-zinc-600">{brief.disclaimer}</p> : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

export { AiBriefPanel }
