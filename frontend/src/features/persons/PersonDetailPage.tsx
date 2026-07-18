import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { BadgeCheck } from "lucide-react"
import { useParams } from "react-router-dom"

import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { usePermission } from "@/lib/hooks/usePermission"
import { fetchPersonById, submitPersonVerification } from "./personsApi"

function PersonDetailPage() {
  const { personId } = useParams<{ personId: string }>()
  const { has } = usePermission()
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

  if (!personId) return <ErrorState message="No person selected." />
  if (isLoading) return <LoadingSkeleton variant="card" rows={1} />
  if (isError || !person) {
    return <ErrorState message={extractApiErrorMessage(error, "Couldn't load this person.")} onRetry={() => void refetch()} />
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <CardTitle>Person Record</CardTitle>
          {!person.human_verified && has("verify_person") ? (
            <Button size="sm" className="gap-1.5" onClick={() => verifyMutation.mutate()} disabled={verifyMutation.isPending}>
              <BadgeCheck className="size-3.5" />
              {verifyMutation.isPending ? "Verifying..." : "Verify identity"}
            </Button>
          ) : null}
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-zinc-900 dark:text-zinc-50">{person.full_name}</h2>
            {person.human_verified ? <Badge variant="affirm">verified</Badge> : <Badge variant="neutral">unverified</Badge>}
          </div>

          {conflictMessage ? <p className="text-xs text-critical-500">{conflictMessage}</p> : null}

          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="section-label">Aliases</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.aliases?.join(", ") || "—"}</dd>
            </div>
            <div>
              <dt className="section-label">Nationality</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.nationality ?? "—"}</dd>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <dt className="section-label">Permanent Address</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.permanent_address ?? "Restricted"}</dd>
            </div>
            <div className="col-span-2 sm:col-span-1">
              <dt className="section-label">Present Address</dt>
              <dd className="text-zinc-700 dark:text-zinc-300">{person.present_address ?? "Restricted"}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  )
}

export { PersonDetailPage }
