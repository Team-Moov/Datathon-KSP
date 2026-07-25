import {
  Banknote,
  BellRing,
  Cog,
  FileText,
  LayoutGrid,
  MessagesSquare,
  Network,
  ScrollText,
  ShieldAlert,
  TrendingUp,
  Users,
  UsersRound,
  Waypoints,
} from "lucide-react"
import type { LucideIcon } from "lucide-react"

import type { Permission } from "@/lib/types/permissions"

export interface NavigationEntry {
  /** i18n key resolved at render time in Sidebar.tsx — this file sits outside
   * the React tree (a static const array), so it can't call useTranslation()
   * itself. Never render `labelKey` directly. */
  labelKey: string
  path: string
  icon: LucideIcon
  requiredPermission?: Permission
}

export interface NavigationGroup {
  labelKey: string
  entries: NavigationEntry[]
}

export const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    labelKey: "nav.groups.operations",
    entries: [
      { labelKey: "nav.overview", path: "/", icon: LayoutGrid },
      { labelKey: "nav.cases", path: "/cases", icon: ScrollText, requiredPermission: "view_case_basic" },
      { labelKey: "nav.persons", path: "/persons", icon: Users },
      { labelKey: "nav.documents", path: "/documents", icon: FileText, requiredPermission: "upload_document" },
      { labelKey: "nav.assistant", path: "/chat", icon: MessagesSquare },
    ],
  },
  {
    labelKey: "nav.groups.analysis",
    entries: [
      { labelKey: "nav.networkExplorer", path: "/network", icon: Waypoints, requiredPermission: "view_network_basic" },
      { labelKey: "nav.globalNetworkGraph", path: "/network/graph", icon: Network, requiredPermission: "view_network_basic" },
      { labelKey: "nav.riskProfiling", path: "/risk", icon: ShieldAlert, requiredPermission: "compute_risk_score" },
      { labelKey: "nav.financialCrime", path: "/financial", icon: Banknote, requiredPermission: "view_financial_raw" },
      { labelKey: "nav.trendsForecasting", path: "/trends", icon: TrendingUp, requiredPermission: "view_trends_hotspots" },
      { labelKey: "nav.earlyWarningAlerts", path: "/alerts", icon: BellRing, requiredPermission: "view_network_advanced" },
      { labelKey: "nav.sociologicalInsights", path: "/socio", icon: UsersRound, requiredPermission: "view_aggregate_analytics" },
    ],
  },
  {
    labelKey: "nav.groups.governance",
    entries: [
      { labelKey: "nav.auditLog", path: "/admin/audit-log", icon: ScrollText, requiredPermission: "view_audit_log" },
      { labelKey: "nav.userManagement", path: "/admin/users", icon: Users, requiredPermission: "manage_users" },
      { labelKey: "nav.systemJobs", path: "/admin/jobs", icon: Cog, requiredPermission: "manage_analytics_jobs" },
    ],
  },
]
