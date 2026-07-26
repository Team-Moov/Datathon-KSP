import * as React from "react"
import { Navigate, useLocation } from "react-router-dom"

import { useAuth } from "@/features/auth/AuthProvider"
import { usePermission } from "@/lib/hooks/usePermission"
import type { Permission } from "@/lib/types/permissions"

function FullScreenSpinnerFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-100 dark:bg-zinc-950">
      <div className="glass-surface flex items-center gap-2 rounded-md px-4 py-2.5 text-sm text-zinc-500 dark:text-zinc-400">
        Loading session...
      </div>
    </div>
  )
}

/**
 * Blocks unauthenticated users at the layout boundary rather than per-page.
 * Also catches Catalyst social-login signups that haven't picked their RBAC
 * role yet (see backend/app/api/v1/endpoints/auth.py's exchange_catalyst_identity)
 * and routes them to /auth/select-role before they can reach anything else.
 */
function RequireAuthenticatedSession({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isSessionLoading, currentUser } = useAuth()
  const location = useLocation()

  if (isSessionLoading) return <FullScreenSpinnerFallback />
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />
  if (currentUser?.needs_role_selection) return <Navigate to="/auth/select-role" replace />
  return <>{children}</>
}

/**
 * Route-level enforcement matching the sidebar's nav gating — a direct URL hit
 * is blocked identically to a hidden nav item. The server is still the real
 * enforcement boundary; this only avoids rendering a page that would 403.
 */
function RequirePermission({ permission, children }: { permission: Permission; children: React.ReactNode }) {
  const { has } = usePermission()
  if (!has(permission)) return <Navigate to="/" replace />
  return <>{children}</>
}

export { RequireAuthenticatedSession, RequirePermission, FullScreenSpinnerFallback }
