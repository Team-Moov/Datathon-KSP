import * as React from "react"
import { useMutation } from "@tanstack/react-query"
import { ShieldAlert } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ShapDecompositionBars } from "@/components/charts/ShapDecompositionBars"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { usePermission } from "@/lib/hooks/usePermission"
import { computePersonRiskScore, markRiskScoreReviewed } from "./riskApi"

function RiskProfilingPage() {
  const { has } = usePermission()
  const [personId, setPersonId] = React.useState("")

  const computeMutation = useMutation({ mutationFn: () => computePersonRiskScore(personId.trim()) })
  const reviewMutation = useMutation({
    mutationFn: () => markRiskScoreReviewed(personId.trim(), computeMutation.data!.score_id),
  })

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Risk Profiling</h1>
      <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
        Central-Eight-informed, CHI-weighted risk assessment for investigative attention only — never a standalone
        decision. Protected demographic attributes are never used as model features.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Compute Assessment</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-1.5">
              <Label htmlFor="risk-person-id">Person ID</Label>
              <Input id="risk-person-id" value={personId} onChange={(event) => setPersonId(event.target.value)} placeholder="UUID" />
            </div>
            <Button onClick={() => computeMutation.mutate()} disabled={!personId.trim() || computeMutation.isPending}>
              {computeMutation.isPending ? "Computing..." : "Compute score"}
            </Button>
          </div>

          {computeMutation.isError ? (
            <p className="text-xs text-critical-500">{extractApiErrorMessage(computeMutation.error)}</p>
          ) : null}

          {!computeMutation.data && !computeMutation.isPending ? (
            <EmptyState icon={ShieldAlert} title="No assessment computed yet" description="Enter a person ID and compute a versioned risk score." />
          ) : null}

          {computeMutation.data ? (
            <div className="flat-surface space-y-4 rounded-md p-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
                    {(computeMutation.data.score * 100).toFixed(0)}
                    <span className="text-sm font-normal text-zinc-400"> / 100</span>
                  </p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">Model {computeMutation.data.model_version}</p>
                </div>
                {computeMutation.data.human_reviewed ? (
                  <Badge variant="affirm">reviewed</Badge>
                ) : has("review_risk_score") ? (
                  <Button size="sm" variant="outline" onClick={() => reviewMutation.mutate()} disabled={reviewMutation.isPending}>
                    {reviewMutation.isPending ? "Marking..." : "Mark reviewed"}
                  </Button>
                ) : (
                  <Badge variant="caution">pending review</Badge>
                )}
              </div>

              <ShapDecompositionBars decomposition={computeMutation.data.shap_decomposition} />

              <p className="text-[11px] italic text-zinc-400 dark:text-zinc-600">{computeMutation.data.disclaimer}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  )
}

export { RiskProfilingPage }
