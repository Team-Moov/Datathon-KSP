import {
  Banknote,
  LayoutGrid,
  MessagesSquare,
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
      { label: "Assistant", path: "/chat", icon: MessagesSquare },
    ],
  },
  {
    label: "Analysis",
    entries: [
      { label: "Network Explorer", path: "/network", icon: Waypoints, requiredPermission: "view_network_basic" },
      { label: "Risk Profiling", path: "/risk", icon: ShieldAlert, requiredPermission: "compute_risk_score" },
      { label: "Financial Crime", path: "/financial", icon: Banknote, requiredPermission: "view_financial_raw" },
      { label: "Trends & Forecasting", path: "/trends", icon: TrendingUp, requiredPermission: "view_trends_hotspots" },
      { label: "Sociological Insights", path: "/socio", icon: UsersRound, requiredPermission: "view_aggregate_analytics" },
    ],
  },
  {
    label: "Governance",
    entries: [
      { label: "Audit Log", path: "/admin/audit-log", icon: ScrollText, requiredPermission: "view_audit_log" },
      { label: "User Management", path: "/admin/users", icon: Users, requiredPermission: "manage_users" },
    ],
  },
]
