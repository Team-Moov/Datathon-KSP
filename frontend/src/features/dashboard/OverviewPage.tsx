import { FolderSearch, MessagesSquare, ScrollText, Waypoints } from "lucide-react"
import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { useAuth } from "@/features/auth/AuthProvider"
import { usePermission } from "@/lib/hooks/usePermission"
import { RANK_LABELS } from "@/lib/types/permissions"
import { useDashboardMetrics } from "./useDashboardMetrics"

function OverviewPage() {
  const { t } = useTranslation()
  const { currentUser } = useAuth()
  const { has } = usePermission()
  const { recentCases, activeInvestigationCount, isLoading, isError, errorMessage, refetch } = useDashboardMetrics()

  const QUICK_ACTIONS = [
    { label: t("dashboard.quickActions.caseRegister"), to: "/cases", icon: ScrollText, requiredPermission: "view_case_basic" as const },
    { label: t("dashboard.quickActions.investigatorAssistant"), to: "/chat", icon: MessagesSquare },
    { label: t("dashboard.quickActions.networkExplorer"), to: "/network", icon: Waypoints, requiredPermission: "view_network_basic" as const },
    { label: t("dashboard.quickActions.personSearch"), to: "/persons", icon: FolderSearch },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          {t("dashboard.welcome", { firstName: currentUser?.full_name.split(" ")[0] })}
        </h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          {t("dashboard.signedInAs", { role: currentUser ? RANK_LABELS[currentUser.role] : "" })}
          {currentUser?.badge_number ? ` · ${currentUser.badge_number}` : ""}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {QUICK_ACTIONS.filter((action) => !action.requiredPermission || has(action.requiredPermission)).map(
          (action) => (
            <Link
              key={action.to}
              to={action.to}
              className="flat-surface flex items-center gap-3 rounded-lg p-4 transition-colors hover:border-accent-300 dark:hover:border-accent-700"
            >
              <div className="glass-surface flex size-9 shrink-0 items-center justify-center rounded-md">
                <action.icon className="size-4 text-accent-600 dark:text-accent-300" />
              </div>
              <span className="text-sm font-medium text-zinc-700 dark:text-zinc-200">{action.label}</span>
            </Link>
          ),
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("dashboard.recentCases")}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingSkeleton variant="list" rows={5} />
          ) : isError ? (
            <ErrorState message={errorMessage ?? t("dashboard.noCaptionDesc")} onRetry={() => void refetch()} />
          ) : recentCases.length === 0 ? (
            <EmptyState
              title={t("dashboard.noCaption")}
              description={t("dashboard.noCaptionDesc")}
            />
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {recentCases.map((caseSummary) => (
                <li key={caseSummary.id}>
                  <Link
                    to={`/cases/${caseSummary.id}`}
                    className="flex items-center justify-between px-4 py-2.5 text-sm transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                  >
                    <span className="font-mono text-xs text-zinc-500 dark:text-zinc-400">{caseSummary.crime_no}</span>
                    <span className="text-zinc-400 dark:text-zinc-500">{caseSummary.date_reported ?? "—"}</span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      <p className="section-label">{t("dashboard.casesInView", { count: activeInvestigationCount })}</p>
    </div>
  )
}

export { OverviewPage }
