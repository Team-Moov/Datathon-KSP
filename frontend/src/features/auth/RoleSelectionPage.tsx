import * as React from "react"
import { ShieldHalf } from "lucide-react"
import { Navigate, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { RANK_LABELS, type PoliceRank } from "@/lib/types/permissions"
import { selectRole } from "./authApi"
import { useAuth } from "./AuthProvider"
import { FullScreenSpinnerFallback } from "@/app/RouteGuards"

const SELECTABLE_ROLES: PoliceRank[] = [
  "CONSTABLE",
  "INSPECTOR",
  "DSP",
  "SP",
  "DGP",
  "CRIME_ANALYST",
  "POLICY_MAKER",
]

/**
 * One-time role pick shown right after a Catalyst social-login signup —
 * RequireAuthenticatedSession redirects here whenever needs_role_selection is
 * true (see backend/app/api/v1/endpoints/auth.py). Self-service, no approval
 * step — a deliberate demo/onboarding tradeoff, not how production RBAC
 * grants should work.
 */
function RoleSelectionPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { isAuthenticated, isSessionLoading, currentUser, refreshCurrentUser } = useAuth()
  const [selectedRole, setSelectedRole] = React.useState<PoliceRank | null>(null)
  const [isSubmitting, setIsSubmitting] = React.useState(false)
  const [error, setError] = React.useState<string | null>(null)

  if (isSessionLoading) return <FullScreenSpinnerFallback />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  // Role already picked (e.g. back button after confirming) — nothing left to do here.
  if (currentUser && !currentUser.needs_role_selection) return <Navigate to="/" replace />

  async function onConfirm() {
    if (!selectedRole) return
    setIsSubmitting(true)
    setError(null)
    try {
      await selectRole(selectedRole)
      await refreshCurrentUser()
      navigate("/", { replace: true })
    } catch (err) {
      setError(extractApiErrorMessage(err, t("auth.roleSelectionFailed")))
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen flex-col items-center bg-zinc-100 px-4 py-10 dark:bg-zinc-950">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <div className="glass-surface flex size-11 items-center justify-center rounded-lg">
          <ShieldHalf className="size-5 text-accent-600 dark:text-accent-300" />
        </div>
        <div>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{t("auth.roleSelectionTitle")}</p>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">{t("auth.roleSelectionSubtitle")}</p>
        </div>
      </div>

      <div className="grid w-full max-w-2xl grid-cols-1 gap-3 sm:grid-cols-2">
        {SELECTABLE_ROLES.map((role) => (
          <button
            key={role}
            type="button"
            onClick={() => setSelectedRole(role)}
            className={`glass-surface rounded-lg p-4 text-left transition-colors ${
              selectedRole === role
                ? "border-accent-500 ring-1 ring-accent-500"
                : "hover:border-zinc-300 dark:hover:border-zinc-700"
            }`}
          >
            <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{RANK_LABELS[role]}</p>
          </button>
        ))}
      </div>

      {error ? <p className="mt-4 text-xs text-critical-500">{error}</p> : null}

      <Button className="mt-8 w-full max-w-2xl" disabled={!selectedRole || isSubmitting} onClick={onConfirm}>
        {isSubmitting ? t("auth.roleSelectionSubmitting") : t("auth.roleSelectionConfirm")}
      </Button>
    </div>
  )
}

export { RoleSelectionPage }
