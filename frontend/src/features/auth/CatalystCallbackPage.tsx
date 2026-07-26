import * as React from "react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { generateCatalystAuthToken, getCatalystProjectUser } from "@/lib/catalyst/catalystAuth"
import { exchangeCatalystIdentity } from "./authApi"
import { useAuth } from "./AuthProvider"

/**
 * Landing page for Catalyst's embedded login iFrame (see LoginPage's
 * service_url). Reads the now-active Catalyst session and exchanges it for
 * our own token pair via /auth/catalyst/exchange.
 */
function CatalystCallbackPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { applyTokenPair } = useAuth()
  const [error, setError] = React.useState<string | null>(null)

  React.useEffect(() => {
    let cancelled = false

    async function completeCatalystLogin() {
      const catalystUser = await getCatalystProjectUser()
      if (!catalystUser) {
        if (!cancelled) setError(t("auth.catalystNoSession"))
        return
      }
      try {
        const catalystToken = await generateCatalystAuthToken()
        const tokens = await exchangeCatalystIdentity(catalystToken)
        if (cancelled) return
        await applyTokenPair(tokens)
        navigate("/", { replace: true })
      } catch {
        if (!cancelled) setError(t("auth.catalystExchangeFailed"))
      }
    }

    void completeCatalystLogin()
    return () => {
      cancelled = true
    }
  }, [applyTokenPair, navigate, t])

  return (
    <div className="flex min-h-screen items-center justify-center bg-zinc-100 px-4 dark:bg-zinc-950">
      <p className="text-sm text-zinc-500 dark:text-zinc-400">{error ?? t("auth.catalystSigningIn")}</p>
    </div>
  )
}

export { CatalystCallbackPage }
