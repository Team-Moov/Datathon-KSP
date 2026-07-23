import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RefreshCw, ShieldAlert } from "lucide-react"
import { toast } from "sonner"

import { AlertsList } from "@/components/charts/AlertsList"
import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/features/auth/AuthProvider"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { roleHasPermission } from "@/lib/types/permissions"
import {
  acknowledgeAlert,
  dismissAlert,
  fetchAlerts,
  triggerAlertScan,
  type AlertType,
} from "./alertsApi"

const TYPE_FILTERS: { label: string; value: AlertType | "all" }[] = [
  { label: "All", value: "all" },
  { label: "Repeat offenders", value: "repeat_offender" },
  { label: "Organized groups", value: "organized_group" },
]

function AlertsPage() {
  const { currentUser } = useAuth()
  const queryClient = useQueryClient()
  const [typeFilter, setTypeFilter] = React.useState<AlertType | "all">("all")
  const [busyId, setBusyId] = React.useState<string | null>(null)

  const canScan = roleHasPermission(currentUser?.role, "manage_analytics_jobs")

  const alertsQuery = useQuery({
    queryKey: ["alerts", typeFilter],
    queryFn: () => fetchAlerts(typeFilter === "all" ? undefined : { alert_type: typeFilter }),
  })

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["alerts"] })
  }

  const ackMutation = useMutation({
    mutationFn: acknowledgeAlert,
    onMutate: (id: string) => setBusyId(id),
    onSuccess: invalidate,
    onError: (error) => toast.error(extractApiErrorMessage(error)),
    onSettled: () => setBusyId(null),
  })

  const dismissMutation = useMutation({
    mutationFn: dismissAlert,
    onMutate: (id: string) => setBusyId(id),
    onSuccess: invalidate,
    onError: (error) => toast.error(extractApiErrorMessage(error)),
    onSettled: () => setBusyId(null),
  })

  const scanMutation = useMutation({
    mutationFn: triggerAlertScan,
    onSuccess: (data) => {
      toast.success(`Scan complete — ${data.inserted} new alert(s)`)
      invalidate()
    },
    onError: (error) => toast.error(extractApiErrorMessage(error)),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Early-Warning Alerts</h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Proactive signals for repeat offenders and organized groups — every alert traces to a deterministic
            detector, never a guess.
          </p>
        </div>
        {canScan ? (
          <Button
            type="button"
            variant="outline"
            className="gap-1.5"
            disabled={scanMutation.isPending}
            onClick={() => scanMutation.mutate()}
          >
            <RefreshCw className={scanMutation.isPending ? "size-4 animate-spin" : "size-4"} />
            Run scan
          </Button>
        ) : null}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {TYPE_FILTERS.map((filter) => (
          <button
            key={filter.value}
            type="button"
            onClick={() => setTypeFilter(filter.value)}
            className={
              typeFilter === filter.value
                ? "rounded-full bg-accent-600 px-3 py-1 text-xs text-white"
                : "rounded-full border border-zinc-200 px-3 py-1 text-xs text-zinc-500 hover:text-zinc-800 dark:border-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
            }
          >
            {filter.label}
          </button>
        ))}
      </div>

      {alertsQuery.isLoading ? (
        <LoadingSkeleton variant="card" rows={3} />
      ) : alertsQuery.isError ? (
        <ErrorState message={extractApiErrorMessage(alertsQuery.error)} onRetry={() => void alertsQuery.refetch()} />
      ) : !alertsQuery.data || alertsQuery.data.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title="No active alerts"
          description={canScan ? "Run a scan to detect repeat-offender and organized-group signals." : "Nothing is currently flagged for your attention."}
        />
      ) : (
        <AlertsList
          alerts={alertsQuery.data}
          busyId={busyId}
          onAcknowledge={(id) => ackMutation.mutate(id)}
          onDismiss={(id) => dismissMutation.mutate(id)}
        />
      )}
    </div>
  )
}

export { AlertsPage }
