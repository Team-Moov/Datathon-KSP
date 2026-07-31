import * as React from "react"
import { ShieldHalf } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { mountCatalystSignIn } from "@/lib/catalyst/catalystAuth"
import { useAuth } from "./AuthProvider"

const CATALYST_LOGIN_ELEMENT_ID = "catalyst-login"

/**
 * Authentication is exclusively Catalyst's embedded login iFrame — there is
 * no password form here. It only mounts once this app is served through
 * Catalyst Web Client Hosting (see src/lib/catalyst/catalystAuth.ts); local
 * Vite dev and any other hosting show the "unavailable" notice below instead
 * of a blank box.
 */
function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { isAuthenticated } = useAuth()
  const [catalystUnavailable, setCatalystUnavailable] = React.useState(false)

  React.useEffect(() => {
    if (isAuthenticated) {
      navigate("/", { replace: true })
      return
    }
    try {
      mountCatalystSignIn(CATALYST_LOGIN_ELEMENT_ID, {
        service_url: "/auth/catalyst-callback",
        // Zoho's default embedded-signin.css centers a fixed 520px card —
        // this is our copy of that same file with a full-bleed override
        // appended after it, per the documented "style after the last line"
        // convention. Must be an absolute URL: it's fetched by the iframe's
        // own document (a different origin), not by this page.
        css_url: `${window.location.origin}${import.meta.env.BASE_URL}embedded-signin.css`,
      })
    } catch (error) {
      console.debug("Catalyst embedded sign-in unavailable:", error)
      setCatalystUnavailable(true)
    }
  }, [isAuthenticated, navigate])

  return (
    <div className="flex min-h-screen flex-col bg-zinc-100 dark:bg-zinc-950">
      <div className="flex shrink-0 flex-col items-center gap-2 px-4 pt-10 pb-6 text-center">
        <div className="glass-surface flex size-11 items-center justify-center rounded-lg">
          <ShieldHalf className="size-5 text-accent-600 dark:text-accent-300" />
        </div>
        <div>
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{t("auth.title")}</p>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">{t("auth.subtitle")}</p>
        </div>
      </div>

      {catalystUnavailable ? (
        <p className="text-center text-xs text-critical-500">{t("auth.catalystUnavailable")}</p>
      ) : (
        <div id={CATALYST_LOGIN_ELEMENT_ID} className="min-h-0 flex-1" />
      )}
    </div>
  )
}

export { LoginPage }
