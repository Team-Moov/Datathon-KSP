import * as React from "react"
import { ArrowRight, Lock, Network, ScrollText, ShieldHalf, TrendingUp } from "lucide-react"
import { Link, useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { mountCatalystSignIn } from "@/lib/catalyst/catalystAuth"
import { useAuth } from "./AuthProvider"
import {
  clearCatalystExchangeFailure,
  clearSignedOut,
  hasCatalystExchangeFailed,
  hasSignedOut,
} from "./catalystExchangeStatus"

const CATALYST_LOGIN_ELEMENT_ID = "catalyst-login"

/**
 * Shown in plain sight on purpose: this is a hackathon demo over synthetic
 * data, and evaluators need to get in without being handed credentials out of
 * band. Treat this account as disposable and rotate it once judging is over,
 * since anyone who loads this page can read the password.
 */
const DEMO_EMAIL = "siddhantshivam198@gmail.com"
const DEMO_PASSWORD = "Demouserab@123"
const CATALYST_SIGNUP_URL =
  "https://crime-intelligence-platform-60079288389.development.catalystserverless.in/__catalyst/auth/login"

const CAPABILITY_HIGHLIGHTS = [
  { icon: Network, key: "networks" },
  { icon: TrendingUp, key: "trends" },
  { icon: ScrollText, key: "governance" },
] as const

/**
 * Authentication is exclusively Catalyst's embedded login iFrame, so there is
 * no password form here. It only mounts once this app is served through
 * Catalyst Web Client Hosting (see src/lib/catalyst/catalystAuth.ts); local
 * Vite dev and any other hosting show the "unavailable" notice instead of a
 * blank box.
 */
function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { isAuthenticated, isSessionLoading } = useAuth()
  const [catalystUnavailable, setCatalystUnavailable] = React.useState(false)
  const exchangeFailed = hasCatalystExchangeFailed()
  // Held in state, not read live, so clearing it re-renders and mounts the
  // iFrame in place rather than needing a reload.
  const [signedOut, setSignedOut] = React.useState(hasSignedOut)

  React.useEffect(() => {
    // Mounting the iFrame while AuthProvider is still adopting an existing
    // Catalyst session would make Catalyst redirect out from under it, and we
    // would land back here before the exchange ever finished, which is the
    // reload loop. Wait until we know there is no session to adopt.
    if (isSessionLoading) return
    if (isAuthenticated) {
      navigate("/", { replace: true })
      return
    }
    // Signed in to Catalyst but we could not turn that into an app session.
    // Re-mounting the iFrame would just redirect back here, so surface the
    // failure instead and let the loop stop somewhere visible.
    if (exchangeFailed) return
    // Just signed out. Mounting the iFrame here would silently re-authenticate
    // against the still-live Zoho SSO cookie, undoing the sign-out.
    if (signedOut) return
    try {
      mountCatalystSignIn(CATALYST_LOGIN_ELEMENT_ID, {
        // Absolute, and base-path aware for the same reason as css_url below:
        // the app is served under /app/, so a bare "/auth/catalyst-callback"
        // resolves outside the app's basename and never reaches the router.
        service_url: `${window.location.origin}${import.meta.env.BASE_URL}auth/catalyst-callback`,
        // Zoho's default embedded-signin.css centers a fixed 520px card. This
        // is our copy of that same file with a full-bleed override appended
        // after it, per the documented "style after the last line" convention.
        // Must be an absolute URL: it is fetched by the iframe's own document
        // (a different origin), not by this page.
        css_url: `${window.location.origin}${import.meta.env.BASE_URL}embedded-signin.css`,
      })
    } catch (error) {
      console.debug("Catalyst embedded sign-in unavailable:", error)
      setCatalystUnavailable(true)
    }
  }, [isAuthenticated, isSessionLoading, exchangeFailed, signedOut, navigate])

  return (
    <div className="min-h-screen bg-zinc-100 dark:bg-zinc-950">
      <div className="mx-auto grid min-h-screen w-full max-w-6xl grid-cols-1 items-center gap-10 px-5 py-10 lg:grid-cols-[1.05fr_1fr] lg:gap-16 lg:py-14">
        {/* Identity and context. On phones this sits above the sign-in card and
            stays compact; the capability list is the first thing dropped. */}
        <section>
          <div className="flex items-center gap-2.5">
            <div className="glass-surface flex size-10 items-center justify-center rounded-lg">
              <ShieldHalf className="size-5 text-accent-600 dark:text-accent-300" />
            </div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400">
              {t("auth.org")}
            </span>
          </div>

          <h1 className="mt-7 text-3xl font-semibold leading-tight tracking-tight text-zinc-900 sm:text-4xl dark:text-zinc-50">
            {t("auth.title")}
          </h1>
          <p className="mt-3 max-w-md text-sm leading-relaxed text-zinc-600 dark:text-zinc-400">
            {t("auth.tagline")}
          </p>

          <ul className="mt-8 hidden max-w-md space-y-3.5 sm:block">
            {CAPABILITY_HIGHLIGHTS.map(({ icon: Icon, key }) => (
              <li key={key} className="flex items-start gap-3">
                <div className="glass-surface mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-md">
                  <Icon className="size-3.5 text-accent-600 dark:text-accent-300" />
                </div>
                <div>
                  <p className="text-xs font-medium text-zinc-800 dark:text-zinc-100">
                    {t(`auth.highlights.${key}.title`)}
                  </p>
                  <p className="mt-0.5 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                    {t(`auth.highlights.${key}.body`)}
                  </p>
                </div>
              </li>
            ))}
          </ul>

          <Link
            to="/access-scope"
            className="mt-8 inline-flex items-center gap-1.5 text-xs font-medium text-accent-700 transition-colors hover:text-accent-800 dark:text-accent-300 dark:hover:text-accent-200"
          >
            {t("auth.readAccessScope")}
            <ArrowRight className="size-3.5" />
          </Link>
        </section>

        {/* Sign-in surface. The Catalyst iFrame fills #catalyst-login absolutely
            (see globals.css), so this column needs a real height rather than
            relying on the iframe to size itself. */}
        <section className="glass-surface flex min-h-[540px] flex-col overflow-hidden rounded-xl">
          <div className="border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
            <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{t("auth.signInHeading")}</p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-zinc-500 dark:text-zinc-400">
              <Lock className="size-3" />
              {t("auth.subtitle")}
            </p>
          </div>

          {/* Deliberately loud: evaluators land here cold and must be able to
              sign in without being sent credentials separately. */}
          {/* accent-900, not 950: the palette in globals.css stops at 900, and
              an undefined shade silently emits no rule, which left the light
              bg-accent-50 showing in dark mode under near-white text. */}
          <div className="border-b border-accent-300 bg-accent-50 px-5 py-4 dark:border-accent-800 dark:bg-accent-900/40">
            <p className="text-xs font-bold uppercase tracking-wider text-accent-800 dark:text-accent-200">
              {t("auth.demoTitle")}
            </p>
            <dl className="mt-2 space-y-1.5">
              <div className="flex flex-wrap items-baseline gap-x-2">
                <dt className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">{t("auth.demoEmail")}</dt>
                <dd className="select-all break-all font-mono text-sm font-bold text-zinc-900 dark:text-zinc-50">
                  {DEMO_EMAIL}
                </dd>
              </div>
              <div className="flex flex-wrap items-baseline gap-x-2">
                <dt className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">{t("auth.demoPassword")}</dt>
                <dd className="select-all break-all font-mono text-sm font-bold text-zinc-900 dark:text-zinc-50">
                  {DEMO_PASSWORD}
                </dd>
              </div>
            </dl>
            <p className="mt-2.5 text-xs text-zinc-600 dark:text-zinc-400">
              {t("auth.demoSignupPrompt")}{" "}
              {/* External Catalyst-hosted page, not an app route, so a plain
                  anchor is correct here rather than a router Link. */}
              <a
                href={CATALYST_SIGNUP_URL}
                target="_blank"
                rel="noreferrer"
                className="font-semibold text-accent-700 underline underline-offset-2 hover:text-accent-800 dark:text-accent-300 dark:hover:text-accent-200"
              >
                {t("auth.demoSignupLink")}
              </a>
            </p>
          </div>

          {catalystUnavailable ? (
            <div className="flex flex-1 items-center justify-center px-6 py-10">
              <p className="max-w-xs text-center text-xs leading-relaxed text-critical-500">
                {t("auth.catalystUnavailable")}
              </p>
            </div>
          ) : exchangeFailed ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
              <p className="max-w-xs text-xs leading-relaxed text-critical-500">{t("auth.catalystExchangeFailed")}</p>
              <button
                type="button"
                className="glass-surface rounded-md px-3 py-1.5 text-xs text-zinc-700 transition-colors hover:bg-zinc-100 dark:text-zinc-200 dark:hover:bg-zinc-800"
                onClick={() => {
                  clearCatalystExchangeFailure()
                  window.location.reload()
                }}
              >
                {t("common.retry")}
              </button>
            </div>
          ) : signedOut ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
              <p className="text-xs text-zinc-600 dark:text-zinc-300">{t("auth.signedOut")}</p>
              <button
                type="button"
                className="rounded-md bg-accent-600 px-4 py-2 text-xs font-medium text-white transition-colors hover:bg-accent-700"
                onClick={() => {
                  clearSignedOut()
                  setSignedOut(false)
                }}
              >
                {t("auth.signInHeading")}
              </button>
            </div>
          ) : (
            <div id={CATALYST_LOGIN_ELEMENT_ID} className="min-h-0 flex-1" />
          )}
        </section>
      </div>
    </div>
  )
}

export { LoginPage }
