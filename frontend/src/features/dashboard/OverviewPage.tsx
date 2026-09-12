import {
  FolderSearch,
  MessagesSquare,
  ScrollText,
  Waypoints,
  ShieldAlert,
  Activity,
  Users,
  CheckCircle2,
  ArrowRight,
  TrendingUp,
  MapPin,
  Loader2,
} from "lucide-react"
import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"
import { useQuery } from "@tanstack/react-query"
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip, Legend } from "recharts"
import type { NameType, ValueType } from "recharts/types/component/DefaultTooltipContent"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { useAuth } from "@/features/auth/AuthProvider"
import { usePermission } from "@/lib/hooks/usePermission"
import { RANK_LABELS } from "@/lib/types/permissions"
import { fetchAlerts, fetchAlertsSummary } from "@/features/alerts/alertsApi"
import { fetchCaseStats } from "@/features/cases/casesApi"
import { cn } from "@/lib/utils"
import { useDashboardMetrics } from "./useDashboardMetrics"

// Deterministic colors for the pie chart slices (cycling if more than 8 categories).
const SLICE_COLORS = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444",
  "#8b5cf6", "#06b6d4", "#f97316", "#84cc16",
]

function OverviewPage() {
  const { t } = useTranslation()
  const { currentUser } = useAuth()
  const { has } = usePermission()
  const {
    recentCases,
    isLoading: casesLoading,
    isError: casesError,
    errorMessage: casesErrorMsg,
    refetch: refetchCases,
  } = useDashboardMetrics()

  // Real-time alerts
  const alertsQuery = useQuery({
    queryKey: ["dashboard-alerts"],
    queryFn: () => fetchAlerts({ status: "new" }),
  })
  const summaryQuery = useQuery({
    queryKey: ["dashboard-alerts-summary"],
    queryFn: fetchAlertsSummary,
  })

  // Real aggregate stats from the DB — replaces all hardcoded numbers
  const statsQuery = useQuery({
    queryKey: ["dashboard-case-stats"],
    queryFn: fetchCaseStats,
    // Refresh every 5 minutes so the dashboard stays live without hammering the DB
    staleTime: 5 * 60 * 1000,
  })

  const QUICK_ACTIONS = [
    {
      label: t("dashboard.quickActions.caseRegister"),
      to: "/cases",
      icon: ScrollText,
      requiredPermission: "view_case_basic" as const,
      desc: "Browse, register, and track FIR cases across Karnataka police units",
    },
    {
      label: t("dashboard.quickActions.investigatorAssistant"),
      to: "/chat",
      icon: MessagesSquare,
      desc: "Ask the AI copilot for hotspot forecasts, MO trends, or resource-allocation queries in plain language",
    },
    {
      label: t("dashboard.quickActions.networkExplorer"),
      to: "/network",
      icon: Waypoints,
      requiredPermission: "view_network_basic" as const,
      desc: "Visualise multi-jurisdictional syndicate networks and AI-predicted co-offending links",
    },
    {
      label: t("dashboard.quickActions.personSearch"),
      to: "/persons",
      icon: FolderSearch,
      desc: "Look up suspect history, risk scores, and cross-case identity clusters",
    },
    {
      label: "Spatial Hotspot Map",
      to: "/trends",
      icon: MapPin,
      requiredPermission: "view_aggregate_analytics" as const,
      desc: "View Hawkes-ETAS near-repeat forecasts on the district map with predicted risk cells",
    },
    {
      label: "Crime Trends & Analytics",
      to: "/trends",
      icon: TrendingUp,
      requiredPermission: "view_aggregate_analytics" as const,
      desc: "Day-of-week, monthly, and hourly crime patterns. Identify when and where crime peaks",
    },
  ]

  const activeAlertsCount = summaryQuery.data?.new ?? 0
  const highSeverityAlerts = summaryQuery.data?.high_severity ?? 0
  const recentAlerts = (alertsQuery.data ?? []).slice(0, 4)

  const totalCases = statsQuery.data?.total_cases ?? null
  const recentCases7d = statsQuery.data?.recent_cases_7d ?? null
  const suspectCount = statsQuery.data?.suspect_count ?? null
  const crimeDistribution = (statsQuery.data?.crime_distribution ?? []).map((item, i) => ({
    ...item,
    color: SLICE_COLORS[i % SLICE_COLORS.length],
  }))

  return (
    <div className="space-y-6">
      {/* Premium Header Greeting */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-150 dark:border-zinc-800 pb-4">
        <div>
          <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-50 tracking-tight">
            Karnataka Crime Platform: Command Center
          </h1>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Logged in as{" "}
            <span className="font-semibold text-zinc-700 dark:text-zinc-350">
              {currentUser ? RANK_LABELS[currentUser.role] : "Officer"}
            </span>
            {currentUser?.badge_number ? ` (Badge: ${currentUser.badge_number})` : ""} · All data
            sourced live from the analytics engine.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/30 dark:text-emerald-400 border border-emerald-100 dark:border-emerald-900 px-2 py-1 rounded">
            <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Hawkes-ETAS Engine Online
          </span>
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold bg-indigo-50 text-indigo-700 dark:bg-indigo-950/30 dark:text-indigo-400 border border-indigo-100 dark:border-indigo-900 px-2 py-1 rounded">
            <span className="size-1.5 rounded-full bg-indigo-500 animate-pulse" />
            GCN Link-Prediction Online
          </span>
          <span className="inline-flex items-center gap-1 text-[11px] font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400 border border-amber-100 dark:border-amber-900 px-2 py-1 rounded">
            <span className="size-1.5 rounded-full bg-amber-500 animate-pulse" />
            Financial AML Scanner Online
          </span>
        </div>
      </div>

      {/* KPI Metrics Row — all from live API */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Metric 1: Total Cases */}
        <Card className="hover:border-zinc-300 dark:hover:border-zinc-700 transition">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-450 dark:text-zinc-500">
              Total Cases (DB)
            </CardTitle>
            <Activity className="h-4 w-4 text-accent-600 dark:text-accent-400" />
          </CardHeader>
          <CardContent>
            {statsQuery.isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
            ) : (
              <>
                <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                  {totalCases !== null ? totalCases.toLocaleString() : "-"}
                </div>
                <p className="text-[10px] text-zinc-450 dark:text-zinc-500 mt-1">
                  {recentCases7d !== null
                    ? `${recentCases7d} filed in last 7 days`
                    : "Loading recent count…"}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Metric 2: Active Threats */}
        <Card
          className={cn(
            "hover:border-zinc-300 dark:hover:border-zinc-700 transition",
            activeAlertsCount > 0 ? "border-rose-500/20 bg-rose-500/[0.01]" : "",
          )}
        >
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-450 dark:text-zinc-500">
              Active Threat Alerts
            </CardTitle>
            <ShieldAlert
              className={cn(
                "h-4 w-4",
                activeAlertsCount > 0 ? "text-rose-500 animate-bounce" : "text-zinc-450",
              )}
            />
          </CardHeader>
          <CardContent>
            {summaryQuery.isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
            ) : (
              <>
                <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                  {activeAlertsCount}
                </div>
                <p className="text-[10px] text-zinc-450 mt-1">
                  {highSeverityAlerts > 0 ? (
                    <span className="text-rose-600 dark:text-rose-450 font-semibold">
                      {highSeverityAlerts} high-severity · Action required
                    </span>
                  ) : (
                    <span>No high-severity threats pending</span>
                  )}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Metric 3: Monitored Suspects (from DB) */}
        <Card className="hover:border-zinc-300 dark:hover:border-zinc-700 transition">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-450 dark:text-zinc-500">
              Accused Persons (DB)
            </CardTitle>
            <Users className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          </CardHeader>
          <CardContent>
            {statsQuery.isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
            ) : (
              <>
                <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                  {suspectCount !== null ? suspectCount.toLocaleString() : "-"}
                </div>
                <p className="text-[10px] text-zinc-450 dark:text-zinc-500 mt-1">
                  Unique resolved identities · cross-case
                </p>
              </>
            )}
          </CardContent>
        </Card>

        {/* Metric 4: Alert Total */}
        <Card className="hover:border-zinc-300 dark:hover:border-zinc-700 transition">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-450 dark:text-zinc-500">
              Total Alerts Generated
            </CardTitle>
            <CheckCircle2 className="h-4 w-4 text-indigo-650 dark:text-indigo-400" />
          </CardHeader>
          <CardContent>
            {summaryQuery.isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
            ) : (
              <>
                <div className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">
                  {summaryQuery.data?.active_total ?? "-"}
                </div>
                <p className="text-[10px] text-zinc-450 dark:text-zinc-500 mt-1">
                  Co-offending, structuring &amp; hotspot signals
                </p>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Recent Cases & Alerts Feed */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Left: Recent Cases (7 Cols) */}
        <Card className="lg:col-span-7">
          <CardHeader className="flex flex-row items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
            <div>
              <CardTitle className="text-sm font-semibold">Recent Registrations</CardTitle>
              <CardDescription className="text-[11px]">
                Latest FIR filings across Karnataka police units
              </CardDescription>
            </div>
            <Link
              to="/cases"
              className="text-xs text-accent-650 hover:underline dark:text-accent-400 inline-flex items-center gap-1"
            >
              View all cases <ArrowRight className="size-3" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {casesLoading ? (
              <LoadingSkeleton variant="list" rows={5} />
            ) : casesError ? (
              <ErrorState
                message={casesErrorMsg ?? t("dashboard.noCaptionDesc")}
                onRetry={() => void refetchCases()}
              />
            ) : recentCases.length === 0 ? (
              <EmptyState
                title={t("dashboard.noCaption")}
                description={t("dashboard.noCaptionDesc")}
              />
            ) : (
              <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
                {recentCases.map((caseSummary) => (
                  <li
                    key={caseSummary.id}
                    className="hover:bg-zinc-50 dark:hover:bg-zinc-900/40 transition-colors"
                  >
                    <Link
                      to={`/cases/${caseSummary.id}`}
                      className="flex items-center justify-between px-4 py-3 text-xs"
                    >
                      <div className="space-y-1">
                        <span className="font-mono text-zinc-800 dark:text-zinc-200 font-bold bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
                          {caseSummary.crime_no}
                        </span>
                        <p className="text-[10px] text-zinc-450 dark:text-zinc-500 mt-1">
                          {caseSummary.district_name || "Unknown District"} ·{" "}
                          {caseSummary.crime_group || "Property Offense"}
                        </p>
                      </div>
                      <span className="text-[11px] text-zinc-450 dark:text-zinc-500 font-medium">
                        {caseSummary.date_reported ?? "-"}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        {/* Right: Active Threats Feed (5 Cols) */}
        <Card className="lg:col-span-5">
          <CardHeader className="flex flex-row items-center justify-between border-b border-zinc-100 dark:border-zinc-800 pb-3">
            <div>
              <CardTitle className="text-sm font-semibold">Threat Intelligence Inbox</CardTitle>
              <CardDescription className="text-[11px]">
                Real-time co-offending &amp; structuring anomalies detected by analytics engine
              </CardDescription>
            </div>
            <Link
              to="/alerts"
              className="text-xs text-accent-650 hover:underline dark:text-accent-400 inline-flex items-center gap-1"
            >
              Alerts Console <ArrowRight className="size-3" />
            </Link>
          </CardHeader>
          <CardContent className="p-0">
            {alertsQuery.isLoading ? (
              <LoadingSkeleton variant="list" rows={3} />
            ) : alertsQuery.isError ? (
              <p className="p-4 text-xs text-rose-500">Failed to load active threat stream.</p>
            ) : recentAlerts.length === 0 ? (
              <div className="p-8 text-center">
                <p className="text-xs text-zinc-400 font-medium">No new alerts raised. All clear.</p>
                <p className="text-[10px] text-zinc-400 mt-1">
                  The analytics engine scans continuously. New anomalies will appear here.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
                {recentAlerts.map((alert) => (
                  <li key={alert.id} className="p-3.5 hover:bg-zinc-50 dark:hover:bg-zinc-900/40 transition">
                    <Link to="/alerts" className="block space-y-1.5">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded-full text-[9px] font-bold uppercase",
                            alert.severity === "high"
                              ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-350"
                              : alert.severity === "medium"
                                ? "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-350"
                                : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
                          )}
                        >
                          {alert.severity} Severity
                        </span>
                        <span className="text-[10px] text-zinc-400 font-mono">
                          {alert.created_at ? new Date(alert.created_at).toLocaleTimeString() : ""}
                        </span>
                      </div>
                      <h4 className="text-xs font-bold text-zinc-800 dark:text-zinc-200">
                        {alert.title}
                      </h4>
                      <p className="text-[10px] text-zinc-450 dark:text-zinc-500 leading-normal line-clamp-2">
                        {alert.description}
                      </p>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Analytics Row: Crime Category Mix + Quick Actions */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-12">
        {/* Crime Head Breakdown — from live DB via /cases/stats */}
        <Card className="md:col-span-5">
          <CardHeader className="pb-1">
            <CardTitle className="text-sm font-semibold">Incident Category Mix</CardTitle>
            <CardDescription className="text-[11px]">
              Distribution of registered cases by crime head, sourced live from the database.
              Hover a slice to see the exact count.
            </CardDescription>
          </CardHeader>
          <CardContent className="h-[220px] flex items-center justify-center">
            {statsQuery.isLoading ? (
              <LoadingSkeleton variant="card" rows={1} />
            ) : crimeDistribution.length === 0 ? (
              <EmptyState
                title="No crime data yet"
                description="Register cases to see the category breakdown here."
              />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={crimeDistribution}
                    cx="50%"
                    cy="45%"
                    innerRadius={48}
                    outerRadius={72}
                    paddingAngle={3}
                    dataKey="value"
                    label={({ percent }) =>
                      percent !== undefined && percent > 0.08 ? `${(percent * 100).toFixed(0)}%` : ""
                    }
                    labelLine={false}
                  >
                    {crimeDistribution.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "#18181b",
                      borderColor: "#27272a",
                      borderRadius: "6px",
                    }}
                    itemStyle={{ color: "#f4f4f5", fontSize: "11px" }}
                    formatter={(value: ValueType | undefined, name: NameType | undefined) => [
                      `${value ?? 0} cases`,
                      name ?? "",
                    ]}
                  />
                  <Legend
                    verticalAlign="bottom"
                    height={40}
                    iconSize={8}
                    iconType="circle"
                    wrapperStyle={{ fontSize: "9px", paddingTop: "4px" }}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Quick Actions Panel */}
        <Card className="md:col-span-7">
          <CardHeader>
            <CardTitle className="text-sm font-semibold">Analytical Quick Actions</CardTitle>
            <CardDescription className="text-[11px]">
              Direct links to operational intelligence panels. Your access level determines which
              panels are available.
            </CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {QUICK_ACTIONS.filter(
              (action) => !action.requiredPermission || has(action.requiredPermission),
            ).map((action) => (
              <Link
                key={action.to + action.label}
                to={action.to}
                className="flat-surface flex flex-col gap-1 rounded-lg p-3 transition border border-zinc-200 dark:border-zinc-800 hover:border-accent-300 dark:hover:border-accent-700 bg-white dark:bg-zinc-950/20"
              >
                <div className="flex items-center gap-2">
                  <div className="glass-surface flex size-7 shrink-0 items-center justify-center rounded-md bg-zinc-50 dark:bg-zinc-900">
                    <action.icon className="size-3.5 text-accent-600 dark:text-accent-300" />
                  </div>
                  <span className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
                    {action.label}
                  </span>
                </div>
                <span className="text-[10px] text-zinc-450 dark:text-zinc-500 mt-1 leading-normal">
                  {action.desc}
                </span>
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export { OverviewPage }
