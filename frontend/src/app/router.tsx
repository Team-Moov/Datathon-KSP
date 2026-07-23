import * as React from "react"
import { Route, Routes } from "react-router-dom"

import { DashboardLayout } from "@/layouts/DashboardLayout"
import { FullScreenSpinnerFallback, RequireAuthenticatedSession, RequirePermission } from "./RouteGuards"

const LoginPage = React.lazy(() => import("@/features/auth/LoginPage").then((m) => ({ default: m.LoginPage })))
const OverviewPage = React.lazy(() =>
  import("@/features/dashboard/OverviewPage").then((m) => ({ default: m.OverviewPage })),
)
const CaseListPage = React.lazy(() =>
  import("@/features/cases/CaseListPage").then((m) => ({ default: m.CaseListPage })),
)
const CaseWorkspacePage = React.lazy(() =>
  import("@/features/cases/CaseWorkspacePage").then((m) => ({ default: m.CaseWorkspacePage })),
)
const PersonSearchPage = React.lazy(() =>
  import("@/features/persons/PersonSearchPage").then((m) => ({ default: m.PersonSearchPage })),
)
const PersonDetailPage = React.lazy(() =>
  import("@/features/persons/PersonDetailPage").then((m) => ({ default: m.PersonDetailPage })),
)
const NetworkExplorerPage = React.lazy(() =>
  import("@/features/network/NetworkExplorerPage").then((m) => ({ default: m.NetworkExplorerPage })),
)
const GlobalNetworkPage = React.lazy(() =>
  import("@/features/network/GlobalNetworkPage").then((m) => ({ default: m.GlobalNetworkPage })),
)
const DocumentsPage = React.lazy(() =>
  import("@/features/documents/DocumentsPage").then((m) => ({ default: m.DocumentsPage })),
)
const RiskProfilingPage = React.lazy(() =>
  import("@/features/risk/RiskProfilingPage").then((m) => ({ default: m.RiskProfilingPage })),
)
const FinancialCrimePage = React.lazy(() =>
  import("@/features/financial/FinancialCrimePage").then((m) => ({ default: m.FinancialCrimePage })),
)
const CrimeTrendsPage = React.lazy(() =>
  import("@/features/trends/CrimeTrendsPage").then((m) => ({ default: m.CrimeTrendsPage })),
)
const AlertsPage = React.lazy(() => import("@/features/alerts/AlertsPage").then((m) => ({ default: m.AlertsPage })))
const ModelsPage = React.lazy(() => import("@/features/models/ModelsPage").then((m) => ({ default: m.ModelsPage })))
const SocioInsightsPage = React.lazy(() =>
  import("@/features/socio/SocioInsightsPage").then((m) => ({ default: m.SocioInsightsPage })),
)
const InvestigatorAssistantPage = React.lazy(() =>
  import("@/features/chat/InvestigatorAssistantPage").then((m) => ({ default: m.InvestigatorAssistantPage })),
)
const AuditLogPage = React.lazy(() =>
  import("@/features/admin/AuditLogPage").then((m) => ({ default: m.AuditLogPage })),
)
const UserManagementPage = React.lazy(() =>
  import("@/features/admin/UserManagementPage").then((m) => ({ default: m.UserManagementPage })),
)
const SystemJobsPage = React.lazy(() =>
  import("@/features/admin/SystemJobsPage").then((m) => ({ default: m.SystemJobsPage })),
)

function AppRouter() {
  return (
    <React.Suspense fallback={<FullScreenSpinnerFallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route
          element={
            <RequireAuthenticatedSession>
              <DashboardLayout />
            </RequireAuthenticatedSession>
          }
        >
          <Route path="/" element={<OverviewPage />} />
          <Route path="/cases" element={<CaseListPage />} />
          <Route path="/cases/:caseId" element={<CaseWorkspacePage />} />
          <Route path="/persons" element={<PersonSearchPage />} />
          <Route path="/persons/:personId" element={<PersonDetailPage />} />
          <Route
            path="/documents"
            element={
              <RequirePermission permission="upload_document">
                <DocumentsPage />
              </RequirePermission>
            }
          />

          <Route
            path="/network"
            element={
              <RequirePermission permission="view_network_basic">
                <NetworkExplorerPage />
              </RequirePermission>
            }
          />
          <Route
            path="/network/graph"
            element={
              <RequirePermission permission="view_network_basic">
                <GlobalNetworkPage />
              </RequirePermission>
            }
          />
          <Route
            path="/risk"
            element={
              <RequirePermission permission="compute_risk_score">
                <RiskProfilingPage />
              </RequirePermission>
            }
          />
          <Route
            path="/financial"
            element={
              <RequirePermission permission="view_financial_raw">
                <FinancialCrimePage />
              </RequirePermission>
            }
          />
          <Route
            path="/trends"
            element={
              <RequirePermission permission="view_trends_hotspots">
                <CrimeTrendsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/alerts"
            element={
              <RequirePermission permission="view_network_advanced">
                <AlertsPage />
              </RequirePermission>
            }
          />
          <Route
            path="/socio"
            element={
              <RequirePermission permission="view_aggregate_analytics">
                <SocioInsightsPage />
              </RequirePermission>
            }
          />
          <Route path="/chat" element={<InvestigatorAssistantPage />} />
          <Route path="/models" element={<ModelsPage />} />

          <Route
            path="/admin/audit-log"
            element={
              <RequirePermission permission="view_audit_log">
                <AuditLogPage />
              </RequirePermission>
            }
          />
          <Route
            path="/admin/users"
            element={
              <RequirePermission permission="manage_users">
                <UserManagementPage />
              </RequirePermission>
            }
          />
          <Route
            path="/admin/jobs"
            element={
              <RequirePermission permission="manage_analytics_jobs">
                <SystemJobsPage />
              </RequirePermission>
            }
          />
        </Route>
      </Routes>
    </React.Suspense>
  )
}

export { AppRouter }
