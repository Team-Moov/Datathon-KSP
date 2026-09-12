import * as React from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { useAuth } from "./AuthProvider"
import { getAuthFailureReason } from "./catalystExchangeStatus"

/**
 * Landing page for Catalyst's embedded login iFrame (see LoginPage's
 * service_url). The Catalyst-session → app-token exchange itself lives in
 * AuthProvider's bootstrap, because Catalyst can land a freshly signed-in
 * user on index.html (its login_redirect) just as easily as here — doing it
 * in only one of those places left the other looping back to /login. This
 * page just waits on that shared bootstrap and reports the outcome.
 *
 * ⚠️ The backend trusts whatever identity is sent without independent
 * server-side verification (see that endpoint's docstring) — this is a
 * client-asserted identity, not a server-verified token exchange. Reading the
 * browser's own Catalyst session is legitimate; it's that nothing re-checks
 * it server-side that's the gap.
 */
function CatalystCallbackPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { isAuthenticated, isSessionLoading } = useAuth()

  React.useEffect(() => {
    if (isSessionLoading) return
    if (isAuthenticated) navigate("/", { replace: true })
  }, [isAuthenticated, isSessionLoading, navigate])

  // Report the actual reason. "No active Catalyst session" was shown for all
  // three failures, including a rejected exchange, which sent debugging in
  // entirely the wrong direction.
  const failure = !isSessionLoading && !isAuthenticated ? getAuthFailureReason() : null
  const error = failure
    ? failure.reason === "exchange_failed"
      ? `${t("auth.catalystExchangeFailed")} ${failure.detail ?? ""}`.trim()
      : failure.reason === "signed_out"
        ? t("auth.signedOut")
        : t("auth.catalystNoProjectUser")
    : !isSessionLoading && !isAuthenticated
      ? t("auth.catalystNoSession")
      : null

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-100 px-4 dark:bg-zinc-950">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">{error ?? t("auth.catalystSigningIn")}</p>
    </div>
  )
}

export { CatalystCallbackPage }
