import * as React from "react"
import { useMutation } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { RotateCw, ShieldAlert } from "lucide-react"
import { useSearchParams } from "react-router-dom"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ShapDecompositionBars } from "@/components/charts/ShapDecompositionBars"
import { PersonPicker, type PickedPerson } from "@/components/inputs/PersonPicker"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { usePermission } from "@/lib/hooks/usePermission"
import { computePersonRiskScore, markRiskScoreReviewed } from "./riskApi"

function RiskProfilingPage() {
  const { t } = useTranslation()
  const { has } = usePermission()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selected, setSelected] = React.useState<PickedPerson | null>(null)

  const computeMutation = useMutation({ mutationFn: (personId: string) => computePersonRiskScore(personId) })
  const reviewMutation = useMutation({
    mutationFn: () => markRiskScoreReviewed(selected!.id, computeMutation.data!.score_id),
  })

  // Hydrate from a deep link (?person=<id>&name=<name>) and auto-run once, so a
  // click from the person page / a chat widget / an alert lands on a finished
  // score rather than a blank form. Runs a single time on mount.
  const hydratedRef = React.useRef(false)
  React.useEffect(() => {
    if (hydratedRef.current) return
    hydratedRef.current = true
    const personId = searchParams.get("person")
    if (personId) {
      const person = { id: personId, name: searchParams.get("name") || "Selected person" }
      setSelected(person)
      computeMutation.mutate(personId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleSelect(person: PickedPerson) {
    setSelected(person)
    // Keep the URL shareable/bookmarkable — the exact assessment is reproducible.
    setSearchParams((prev) => {
      prev.set("person", person.id)
      prev.set("name", person.name)
      return prev
    })
    computeMutation.mutate(person.id)
  }

  function handleClear() {
    setSelected(null)
    computeMutation.reset()
    setSearchParams((prev) => {
      prev.delete("person")
      prev.delete("name")
      return prev
    })
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("risk.title")}</h1>
      <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
        {t("risk.description")}
      </p>

      <Card>
        <CardHeader>
          <CardTitle>{t("risk.computeAssessment")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-end gap-3">
            <div className="flex-1 space-y-1.5">
              <p className="section-label">{t("risk.person") || "Person"}</p>
              <PersonPicker selected={selected} onSelect={handleSelect} onClear={handleClear} />
            </div>
            {selected ? (
              <Button
                variant="outline"
                className="gap-1.5"
                onClick={() => computeMutation.mutate(selected.id)}
                disabled={computeMutation.isPending}
              >
                <RotateCw className={computeMutation.isPending ? "size-4 animate-spin" : "size-4"} />
                {t("risk.recompute") || "Recompute"}
              </Button>
            ) : null}
          </div>

          {computeMutation.isError ? (
            <p className="text-xs text-critical-500">{extractApiErrorMessage(computeMutation.error)}</p>
          ) : null}

          {!selected && !computeMutation.data ? (
            <EmptyState
              icon={ShieldAlert}
              title={t("risk.noAssessment")}
              description={t("risk.assessmentDesc")}
            />
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
