import * as React from "react"
import { AlertTriangle, Check, Users, X } from "lucide-react"
import { useTranslation } from "react-i18next"

import { cn } from "@/lib/utils"

export interface AlertListItem {
  id: string
  alert_type: string
  severity: string
  status: string
  title: string
  description: string
  confidence?: number | null
  source_tool?: string
  created_at?: string | null
}

const SEVERITY_STYLES: Record<string, string> = {
  high: "border-caution-500/50 bg-caution-500/10 text-caution-600 dark:text-caution-500",
  medium: "border-caution-500/25 bg-caution-500/5 text-caution-600/80 dark:text-caution-500/80",
  low: "border-zinc-300 bg-zinc-50 text-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400",
}

const TYPE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  organized_group: Users,
  repeat_offender: AlertTriangle,
}

function AlertsList({
  alerts,
  onAcknowledge,
  onDismiss,
  busyId,
}: {
  alerts: AlertListItem[]
  onAcknowledge?: (id: string) => void
  onDismiss?: (id: string) => void
  busyId?: string | null
}) {
  const { t } = useTranslation()
  if (alerts.length === 0) {
    return <p className="px-1 py-2 text-xs text-zinc-400">{t("alertsList.noActiveAlerts")}</p>
  }
  return (
    <ul className="space-y-2">
      {alerts.map((alert) => {
        const Icon = TYPE_ICON[alert.alert_type] ?? AlertTriangle
        const isBusy = busyId === alert.id
        return (
          <li
            key={alert.id}
            className={cn(
              "rounded-md border px-3 py-2",
              SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.low,
            )}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex min-w-0 items-start gap-2">
                <Icon className="mt-0.5 size-4 shrink-0" />
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-zinc-800 dark:text-zinc-100">{alert.title}</p>
                  <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{alert.description}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide text-zinc-400">
                    <span>{alert.severity}</span>
                    <span>·</span>
                    <span>{alert.alert_type.replace(/_/g, " ")}</span>
                    {alert.status === "acknowledged" ? (
                      <>
                        <span>·</span>
                        <span className="text-zinc-500 dark:text-zinc-300">{t("alertsList.acknowledged")}</span>
                      </>
                    ) : null}
                    {typeof alert.confidence === "number" ? (
                      <>
                        <span>·</span>
                        <span>{t("alertsList.conf")} {(alert.confidence * 100).toFixed(0)}%</span>
                      </>
                    ) : null}
                  </div>
                </div>
              </div>
              {onAcknowledge || onDismiss ? (
                <div className="flex shrink-0 items-center gap-1">
                  {onAcknowledge && alert.status !== "acknowledged" ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onAcknowledge(alert.id)}
                      title={t("alertsList.acknowledge")}
                      className="rounded p-1 text-zinc-500 hover:bg-black/5 hover:text-zinc-800 disabled:opacity-40 dark:hover:bg-white/5 dark:hover:text-zinc-100"
                    >
                      <Check className="size-3.5" />
                    </button>
                  ) : null}
                  {onDismiss ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onDismiss(alert.id)}
                      title={t("alertsList.dismiss")}
                      className="rounded p-1 text-zinc-500 hover:bg-black/5 hover:text-zinc-800 disabled:opacity-40 dark:hover:bg-white/5 dark:hover:text-zinc-100"
                    >
                      <X className="size-3.5" />
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>
          </li>
        )
      })}
    </ul>
  )
}

export { AlertsList }
