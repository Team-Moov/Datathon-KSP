import {
  Banknote,
  BellRing,
  Cog,
  Cpu,
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
  label: string
  path: string
  icon: LucideIcon
  requiredPermission?: Permission
}

export interface NavigationGroup {
  label: string
  entries: NavigationEntry[]
}

export const NAVIGATION_GROUPS: NavigationGroup[] = [
  {
    label: "Operations",
    entries: [
      { label: "Overview", path: "/", icon: LayoutGrid },
      { label: "Cases", path: "/cases", icon: ScrollText, requiredPermission: "view_case_basic" },
      { label: "Persons", path: "/persons", icon: Users },
      { label: "Documents", path: "/documents", icon: FileText, requiredPermission: "upload_document" },
      { label: "Assistant", path: "/chat", icon: MessagesSquare },
    ],
  },
  {
    label: "Analysis",
    entries: [
      { label: "Network Explorer", path: "/network", icon: Waypoints, requiredPermission: "view_network_basic" },
      { label: "Global Network Graph", path: "/network/graph", icon: Network, requiredPermission: "view_network_basic" },
      { label: "Risk Profiling", path: "/risk", icon: ShieldAlert, requiredPermission: "compute_risk_score" },
      { label: "Financial Crime", path: "/financial", icon: Banknote, requiredPermission: "view_financial_raw" },
      { label: "Trends & Forecasting", path: "/trends", icon: TrendingUp, requiredPermission: "view_trends_hotspots" },
      { label: "Early-Warning Alerts", path: "/alerts", icon: BellRing, requiredPermission: "view_network_advanced" },
      { label: "Sociological Insights", path: "/socio", icon: UsersRound, requiredPermission: "view_aggregate_analytics" },
    ],
  },
  {
    label: "Governance",
    entries: [
      { label: "Model Transparency", path: "/models", icon: Cpu },
      { label: "Audit Log", path: "/admin/audit-log", icon: ScrollText, requiredPermission: "view_audit_log" },
      { label: "User Management", path: "/admin/users", icon: Users, requiredPermission: "manage_users" },
      { label: "System Jobs", path: "/admin/jobs", icon: Cog, requiredPermission: "manage_analytics_jobs" },
    ],
  },
]
