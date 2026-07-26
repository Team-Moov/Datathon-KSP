import * as React from "react"
import { AlertTriangle, Check, Users, X, ChevronDown, ChevronUp, ExternalLink } from "lucide-react"
import { useTranslation } from "react-i18next"
import { useQuery } from "@tanstack/react-query"
import { Link } from "react-router-dom"

import { cn } from "@/lib/utils"
import { fetchPersonById } from "@/features/persons/personsApi"

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
  evidence?: Record<string, any>
}

const SEVERITY_STYLES: Record<string, string> = {
  high: "border-caution-500/30 bg-caution-500/5 text-caution-600 dark:text-caution-400",
  medium: "border-caution-500/20 bg-caution-500/5 text-caution-650/90 dark:text-caution-400/90",
  low: "border-zinc-200 bg-zinc-50 text-zinc-655 dark:border-zinc-800 dark:bg-zinc-900/60 dark:text-zinc-400",
}

const TYPE_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  organized_group: Users,
  repeat_offender: AlertTriangle,
  financial: AlertTriangle,
}

// Inner helper component to lazy-load and display a person's name by ID
function PersonLink({ personId }: { personId: string }) {
  const { data: person, isLoading } = useQuery({
    queryKey: ["person", personId],
    queryFn: () => fetchPersonById(personId),
  })

  if (isLoading) {
    return <span className="text-xs text-zinc-400 animate-pulse">Loading name...</span>
  }

  if (!person) {
    return <span className="text-xs text-zinc-400 font-mono">ID: {personId.slice(0, 8)}</span>
  }

  return (
    <Link
      to={`/persons/${personId}`}
      className="text-xs text-accent-650 hover:text-accent-700 dark:text-accent-400 dark:hover:text-accent-300 font-medium hover:underline inline-flex items-center gap-0.5"
    >
      {person.full_name || "Unnamed"}
      <ExternalLink className="size-2.5 opacity-60" />
    </Link>
  )
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
  const [expandedAlertId, setExpandedAlertId] = React.useState<string | null>(null)

  if (alerts.length === 0) {
    return <p className="px-1 py-2 text-xs text-zinc-400">{t("alertsList.noActiveAlerts")}</p>
  }

  const toggleExpand = (id: string) => {
    setExpandedAlertId(expandedAlertId === id ? null : id)
  }

  return (
    <ul className="space-y-2.5">
      {alerts.map((alert) => {
        const Icon = TYPE_ICON[alert.alert_type] ?? AlertTriangle
        const isBusy = busyId === alert.id
        const isExpanded = expandedAlertId === alert.id
        const evidence = alert.evidence || {}

        return (
          <li
            key={alert.id}
            className={cn(
              "rounded-md border p-3 transition-all duration-200",
              SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.low,
              "hover:border-zinc-350 dark:hover:border-zinc-700 cursor-pointer"
            )}
            onClick={() => toggleExpand(alert.id)}
          >
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-2.5">
                <Icon className="mt-0.5 size-4 shrink-0 opacity-80" />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">{alert.title}</p>
                    {isExpanded ? (
                      <ChevronUp className="size-3.5 text-zinc-400" />
                    ) : (
                      <ChevronDown className="size-3.5 text-zinc-400" />
                    )}
                  </div>
                  <p className="mt-0.5 text-xs text-zinc-550 dark:text-zinc-450">{alert.description}</p>
                  
                  <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[10px] uppercase tracking-wide text-zinc-400">
                    <span className="font-semibold">{alert.severity} severity</span>
                    <span>·</span>
                    <span>{alert.alert_type.replace(/_/g, " ")}</span>
                    {alert.status === "acknowledged" ? (
                      <>
                        <span>·</span>
                        <span className="text-zinc-500 dark:text-zinc-300 font-semibold">{t("alertsList.acknowledged")}</span>
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
                <div className="flex shrink-0 items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                  {onAcknowledge && alert.status !== "acknowledged" ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onAcknowledge(alert.id)}
                      title={t("alertsList.acknowledge")}
                      className="rounded p-1.5 text-zinc-500 hover:bg-black/5 hover:text-zinc-800 disabled:opacity-40 dark:hover:bg-white/5 dark:hover:text-zinc-100 transition"
                    >
                      <Check className="size-4" />
                    </button>
                  ) : null}
                  {onDismiss ? (
                    <button
                      type="button"
                      disabled={isBusy}
                      onClick={() => onDismiss(alert.id)}
                      title={t("alertsList.dismiss")}
                      className="rounded p-1.5 text-zinc-500 hover:bg-black/5 hover:text-zinc-800 disabled:opacity-40 dark:hover:bg-white/5 dark:hover:text-zinc-100 transition"
                    >
                      <X className="size-4" />
                    </button>
                  ) : null}
                </div>
              ) : null}
            </div>

            {/* Expanded Detailed Insights Block */}
            {isExpanded && (
              <div 
                className="mt-3.5 border-t border-zinc-200/60 dark:border-zinc-800/80 pt-3.5 space-y-3 text-xs"
                onClick={(e) => e.stopPropagation()}
              >
                {/* 1. Organized Group Details */}
                {alert.alert_type === "organized_group" && Array.isArray(evidence.member_person_ids) && (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between gap-2">
                      <h5 className="font-semibold text-zinc-750 dark:text-zinc-250">
                        Co-offending Group Members ({evidence.member_person_ids.length}):
                      </h5>
                    </div>
                    
                    <ul className="grid grid-cols-1 sm:grid-cols-2 gap-2 pl-1 bg-zinc-100/30 dark:bg-zinc-950/20 p-2 rounded border border-zinc-100 dark:border-zinc-900">
                      {evidence.member_person_ids.map((id: string) => (
                        <li key={id} className="flex items-center justify-between gap-3 text-[11px] hover:bg-black/5 dark:hover:bg-white/5 px-2 py-1 rounded transition">
                          <div className="flex items-center gap-1.5 min-w-0">
                            <span className="size-1.5 rounded-full bg-indigo-500 shrink-0" />
                            <PersonLink personId={id} />
                          </div>
                          <Link
                            to={`/network?person=${id}`}
                            className="text-[10px] bg-white border border-zinc-200 hover:bg-zinc-50 text-zinc-500 hover:text-zinc-800 px-2 py-0.5 rounded shadow-sm dark:bg-zinc-850 dark:border-zinc-750 dark:text-zinc-400 dark:hover:text-zinc-200 transition"
                          >
                            Explore Network
                          </Link>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 2. Repeat Offender Details */}
                {alert.alert_type === "repeat_offender" && evidence.person_id && (
                  <div className="bg-zinc-100/30 dark:bg-zinc-950/20 p-3 rounded border border-zinc-100 dark:border-zinc-900 space-y-2">
                    <h5 className="font-semibold text-zinc-750 dark:text-zinc-250">Flagged Offender Details:</h5>
                    <div className="flex items-start justify-between gap-4 flex-wrap">
                      <div className="space-y-1">
                        <p className="text-[11px] text-zinc-550 dark:text-zinc-400">
                          Accused Profile: <PersonLink personId={evidence.person_id} />
                        </p>
                        {evidence.jurisdiction_count && (
                          <p className="text-[11px] text-zinc-550 dark:text-zinc-400">
                            Cross-Jurisdiction Count: <span className="font-semibold text-zinc-850 dark:text-zinc-200">{evidence.jurisdiction_count} Police Units</span>
                          </p>
                        )}
                        {Array.isArray(evidence.units) && (
                          <p className="text-[11px] text-zinc-550 dark:text-zinc-400">
                            Stations Flashed: <span className="font-mono text-zinc-650 dark:text-zinc-350">{evidence.units.join(", ")}</span>
                          </p>
                        )}
                      </div>
                      <Link
                        to={`/network?person=${evidence.person_id}&name=${encodeURIComponent(evidence.name || "Offender")}`}
                        className="bg-accent-600 hover:bg-accent-700 text-white font-medium px-3 py-1.5 rounded shadow-sm text-[11px] transition inline-block text-center"
                      >
                        Explore Network Graph
                      </Link>
                    </div>
                  </div>
                )}

                {/* 3. Financial Alert Details */}
                {alert.alert_type === "financial" && (
                  <div className="space-y-2">
                    <h5 className="font-semibold text-zinc-750 dark:text-zinc-250">Accounts Flagged:</h5>
                    {Array.isArray(evidence.accounts_involved) ? (
                      <ul className="space-y-1.5 bg-zinc-100/30 dark:bg-zinc-950/20 p-2.5 rounded border border-zinc-100 dark:border-zinc-900">
                        {evidence.accounts_involved.map((acc: string) => (
                          <li key={acc} className="flex items-center justify-between text-[11px] text-zinc-600 dark:text-zinc-400">
                            <span className="font-mono bg-zinc-100 dark:bg-zinc-850 px-1 py-0.5 rounded">{acc}</span>
                            <Link
                              to={`/financial`}
                              className="text-[10px] bg-white border border-zinc-200 hover:bg-zinc-50 text-zinc-500 hover:text-zinc-800 px-2 py-0.5 rounded shadow-sm dark:bg-zinc-850 dark:border-zinc-750 dark:text-zinc-400 dark:hover:text-zinc-200 transition"
                            >
                              Open Financial Scan Panel
                            </Link>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-zinc-400 italic">No account numbers recorded in evidence trail.</p>
                    )}
                    {evidence.recommended_action && (
                      <p className="text-[11px] text-zinc-500 dark:text-zinc-400 italic bg-amber-500/5 dark:bg-amber-400/5 p-2 rounded border border-amber-500/10 text-amber-800 dark:text-amber-300">
                        <span className="font-semibold not-italic">Recommended Action:</span> {evidence.recommended_action}
                      </p>
                    )}
                  </div>
                )}

                {/* Metadata block (Common to all alerts) */}
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-zinc-400 bg-zinc-100/10 dark:bg-zinc-900/20 p-2 rounded">
                  {alert.source_tool && (
                    <div>
                      <span className="font-medium text-zinc-450">Detection Tool:</span> <span className="font-mono">{alert.source_tool}</span>
                    </div>
                  )}
                  {alert.created_at && (
                    <div>
                      <span className="font-medium text-zinc-450">Raised:</span> <span>{new Date(alert.created_at).toLocaleString()}</span>
                    </div>
                  )}
                  {alert.id && (
                    <div>
                      <span className="font-medium text-zinc-450">Alert ID:</span> <span className="font-mono">{alert.id.slice(0, 8)}...</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export { AlertsList }
