import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BadgeCheck, Banknote, ShieldAlert, Waypoints } from "lucide-react"
import type { LucideIcon } from "lucide-react"
import { useNavigate, useParams } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { usePermission } from "@/lib/hooks/usePermission"
import type { Permission } from "@/lib/types/permissions"
import { fetchPersonById, submitPersonVerification } from "./personsApi"

function PersonDetailPage() {
  const { t } = useTranslation()
  const { personId } = useParams<{ personId: string }>()
  const { has } = usePermission()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [conflictMessage, setConflictMessage] = React.useState<string | null>(null)

  const queryKey = ["person-detail", personId]
  const { data: person, isLoading, isError, error, refetch } = useQuery({
    queryKey,
    queryFn: () => fetchPersonById(personId ?? ""),
    enabled: Boolean(personId),
  })

  const verifyMutation = useMutation({
    mutationFn: () => submitPersonVerification(personId ?? "", person!.version),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
    onError: (mutationError) => setConflictMessage(extractApiErrorMessage(mutationError)),
  })

  if (!personId) return <ErrorState message={t("persons.noPersonSelected")} />
  if (isLoading) return <LoadingSkeleton variant="card" rows={1} />
  if (isError || !person) {
    return <ErrorState message={extractApiErrorMessage(error, t("persons.couldntLoadPerson"))} onRetry={() => void refetch()} />
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>{t("persons.personRecord")}</CardTitle>
          {!person.human_verified && has("verify_person") ? (
            <Button size="sm" className="gap-1.5" onClick={() => verifyMutation.mutate()} disabled={verifyMutation.isPending}>
              <BadgeCheck className="size-3.5" />
              {verifyMutation.isPending ? t("persons.verifying") : t("persons.verifyIdentity")}
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{person.full_name}</h2>
            {person.human_verified ? <Badge variant="affirm">{t("persons.verified")}</Badge> : <Badge variant="neutral">{t("common.unverified")}</Badge>}
          </div>

          {/* Deep links — carry this person into each analysis tool pre-selected
              (?person=&name=), so the investigator never copies a UUID between pages. */}
          {(() => {
            const target = (path: string) =>
              `${path}?person=${encodeURIComponent(person.id)}&name=${encodeURIComponent(person.full_name)}`
            const allActions: { label: string; path: string; icon: LucideIcon; permission: Permission }[] = [
              { label: t("persons.assessRisk"), path: "/risk", icon: ShieldAlert, permission: "compute_risk_score" },
              { label: t("persons.viewNetwork"), path: "/network", icon: Waypoints, permission: "view_network_basic" },
              { label: t("persons.financialLinks"), path: "/financial", icon: Banknote, permission: "view_financial_raw" },
            ]
            const actions = allActions.filter((action) => has(action.permission))
            if (actions.length === 0) return null
            return (
              <div className="flex flex-wrap gap-2">
                {actions.map((action) => (
                  <Button
                    key={action.path}
                    size="sm"
                    variant="outline"
                    className="gap-1.5"
                    onClick={() => navigate(target(action.path))}
                  >
                    <action.icon className="size-3.5" />
                    {action.label}
                  </Button>
                ))}
              </div>
            )
          })()}

          {conflictMessage ? <p className="text-xs text-critical-500">{conflictMessage}</p> : null}

          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="section-label">{t("persons.aliases")}</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.aliases?.join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="section-label">{t("persons.nationality")}</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.nationality ?? "—"}</dd>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <dt className="section-label">{t("persons.permanentAddress")}</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.permanent_address ?? t("persons.restricted")}</dd>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <dt className="section-label">{t("persons.presentAddress")}</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.present_address ?? t("persons.restricted")}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}

export { PersonDetailPage }
