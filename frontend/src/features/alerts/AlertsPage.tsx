import * as React from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { RefreshCw, ShieldAlert } from "lucide-react"
import { toast } from "sonner"
import { useTranslation } from "react-i18next"

import { AlertsList } from "@/components/charts/AlertsList"
import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Button } from "@/components/ui/button"
import { useAuth } from "@/features/auth/AuthProvider"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { roleHasPermission } from "@/lib/types/permissions"
import { cn } from "@/lib/utils"
import {
  acknowledgeAlert,
  dismissAlert,
  fetchAlerts,
  fetchAlertsSummary,
  triggerAlertScan,
  type AlertType,
  type AlertStatus,
} from "./alertsApi"

function AlertsPage() {
  const { t } = useTranslation()
  const TYPE_FILTERS: { label: string; value: AlertType | "all" }[] = [
    { label: t("alerts.all"), value: "all" },
    { label: t("alerts.repeatOffenders"), value: "repeat_offender" },
    { label: t("alerts.organizedGroups"), value: "organized_group" },
  ]
  const { currentUser } = useAuth()
  const queryClient = useQueryClient()
  const [typeFilter, setTypeFilter] = React.useState<AlertType | "all">("all")
  const [statusFilter, setStatusFilter] = React.useState<AlertStatus>("new")
  const [busyId, setBusyId] = React.useState<string | null>(null)

  const canScan = roleHasPermission(currentUser?.role, "manage_analytics_jobs")

  const alertsQuery = useQuery({
    queryKey: ["alerts", typeFilter, statusFilter],
    queryFn: () => fetchAlerts({
      alert_type: typeFilter === "all" ? undefined : typeFilter,
      status: statusFilter,
    }),
  })

  const summaryQuery = useQuery({
    queryKey: ["alerts-summary"],
    queryFn: fetchAlertsSummary,
  })

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["alerts"] })
    void queryClient.invalidateQueries({ queryKey: ["alerts-summary"] })
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
      toast.success(t("alerts.scanComplete", { count: data.inserted }))
      invalidate()
    },
    onError: (error) => toast.error(extractApiErrorMessage(error)),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("nav.earlyWarningAlerts")}</h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Proactive alerts for multi-jurisdiction suspects, co-offending rings, and financial crime patterns.
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
            {t("alerts.runScan")}
          </Button>
        ) : null}
      </div>

      {/* Tabs Folder bar */}
      <div className="border-b border-zinc-200 dark:border-zinc-800/80 flex flex-col sm:flex-row justify-between items-stretch sm:items-end gap-3">
        <div className="flex space-x-1 border-b sm:border-b-0 border-zinc-100 dark:border-zinc-900">
          <button
            type="button"
            onClick={() => setStatusFilter("new")}
            className={cn(
              "px-4 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5",
              statusFilter === "new"
                ? "border-accent-600 text-accent-600 dark:text-accent-400 dark:border-accent-400"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-100"
            )}
          >
            <span>Inbox / New Leads</span>
            {summaryQuery.data && (
              <span className={cn(
                "px-1.5 py-0.5 text-[10px] rounded-full shrink-0 font-bold",
                statusFilter === "new" ? "bg-accent-100 text-accent-850 dark:bg-accent-950 dark:text-accent-300" : "bg-zinc-100 text-zinc-550 dark:bg-zinc-800 dark:text-zinc-400"
              )}>
                {summaryQuery.data.new}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setStatusFilter("acknowledged")}
            className={cn(
              "px-4 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5",
              statusFilter === "acknowledged"
                ? "border-accent-600 text-accent-600 dark:text-accent-400 dark:border-accent-400"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-100"
            )}
          >
            <span>Accepted Portfolio</span>
            {summaryQuery.data && (
              <span className={cn(
                "px-1.5 py-0.5 text-[10px] rounded-full shrink-0 font-bold",
                statusFilter === "acknowledged" ? "bg-accent-100 text-accent-850 dark:bg-accent-950 dark:text-accent-300" : "bg-zinc-100 text-zinc-550 dark:bg-zinc-800 dark:text-zinc-400"
              )}>
                {summaryQuery.data.active_total - summaryQuery.data.new}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setStatusFilter("dismissed")}
            className={cn(
              "px-4 py-2 text-xs font-semibold border-b-2 transition-all flex items-center gap-1.5",
              statusFilter === "dismissed"
                ? "border-accent-600 text-accent-600 dark:text-accent-400 dark:border-accent-400"
                : "border-transparent text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-100"
            )}
          >
            <span>Dismissed Archive</span>
          </button>
        </div>

        {/* Type Filter Buttons */}
        <div className="flex items-center gap-1 pb-1">
          {TYPE_FILTERS.map((filter) => (
            <button
              key={filter.value}
              type="button"
              onClick={() => setTypeFilter(filter.value)}
              className={cn(
                "rounded px-2.5 py-0.5 text-[11px] font-medium transition",
                typeFilter === filter.value
                  ? "bg-zinc-200 text-zinc-850 dark:bg-zinc-800 dark:text-zinc-100 font-semibold"
                  : "text-zinc-450 hover:text-zinc-700 dark:text-zinc-500 dark:hover:text-zinc-300"
              )}
            >
              {filter.label}
            </button>
          ))}
        </div>
      </div>

      {alertsQuery.isLoading ? (
        <LoadingSkeleton variant="card" rows={3} />
      ) : alertsQuery.isError ? (
        <ErrorState message={extractApiErrorMessage(alertsQuery.error)} onRetry={() => void alertsQuery.refetch()} />
      ) : !alertsQuery.data || alertsQuery.data.length === 0 ? (
        <EmptyState
          icon={ShieldAlert}
          title={statusFilter === "new" ? t("alerts.noActiveAlerts") : "No alerts in this folder."}
          description={canScan && statusFilter === "new" ? t("alerts.runScanPrompt") : "This category is currently empty."}
        />
      ) : (
        <AlertsList
          alerts={alertsQuery.data}
          busyId={busyId}
          onAcknowledge={statusFilter !== "acknowledged" ? (id) => ackMutation.mutate(id) : undefined}
          onDismiss={statusFilter !== "dismissed" ? (id) => dismissMutation.mutate(id) : undefined}
        />
      )}
    </div>
  )
}

export { AlertsPage }
