import * as React from "react"

import {
  AUTH_SESSION_EXPIRED_EVENT,
  clearTokens,
  getRefreshToken,
  setTokenPair,
  subscribeToTokenChanges,
} from "@/lib/api/authTokenStore"
import { getCatalystProjectUser, signOutOfCatalyst } from "@/lib/catalyst/catalystAuth"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import type { AuthenticatedUser } from "@/lib/types/api"
import { exchangeCatalystIdentity, fetchCurrentUser, submitLogout } from "./authApi"
import {
  clearAuthFailureReason,
  clearCatalystExchangeFailure,
  hasCatalystExchangeFailed,
  hasSignedOut,
  markCatalystExchangeFailed,
  markSignedOut,
  setAuthFailureReason,
} from "./catalystExchangeStatus"

interface AuthContextValue {
  currentUser: AuthenticatedUser | null
  isSessionLoading: boolean
  isAuthenticated: boolean
  endSession: () => Promise<void>
  /** Re-fetches /auth/me without touching tokens — used after POST /auth/select-role. */
  refreshCurrentUser: () => Promise<void>
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

/**
 * Upper bound on the Catalyst bootstrap. Without it, an unreachable backend
 * (a request that hangs rather than 404s) leaves isSessionLoading true
 * forever and the whole app sits on "Loading session..." with no way out.
 * Deliberately scoped to this one call rather than a global axios timeout,
 * which would also cut off legitimately slow work like report generation.
 */
const CATALYST_BOOTSTRAP_TIMEOUT_MS = 15_000

function withTimeout<T>(work: Promise<T>, ms: number): Promise<T> {
  return Promise.race([
    work,
    new Promise<never>((_, reject) => setTimeout(() => reject(new Error("Catalyst bootstrap timed out")), ms)),
  ])
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = React.useState<AuthenticatedUser | null>(null)
  const [isSessionLoading, setIsSessionLoading] = React.useState(true)

  const loadProfileFromExistingSession = React.useCallback(async () => {
    if (!getRefreshToken()) {
      // No app session yet — but Catalyst may have already signed this user
      // in and bounced them back to one of ITS landing pages (index.html via
      // client-package.json's login_redirect, or the embedded iFrame's
      // service_url). Adopting that identity here, rather than only in
      // CatalystCallbackPage, is what makes the app recover no matter which
      // page Catalyst chose: landing anywhere else used to fall through to
      // /login, which re-mounted the iFrame, which redirected again — an
      // endless full-page reload loop.
      // Don't retry an exchange that already failed this tab, and don't adopt a
      // lingering Catalyst session after a deliberate sign-out. Either would
      // put the user straight back into the app they just left.
      const skipAdoption = hasCatalystExchangeFailed() || hasSignedOut()
      const catalystUser = skipAdoption ? null : await getCatalystProjectUser()
      if (!catalystUser) {
        setAuthFailureReason(hasSignedOut() ? "signed_out" : "no_project_user")
        setCurrentUser(null)
        setIsSessionLoading(false)
        return
      }
      try {
        await withTimeout(
          (async () => {
            const tokens = await exchangeCatalystIdentity({
              email: catalystUser.email_id,
              zuid: catalystUser.zuid,
              first_name: catalystUser.first_name,
              last_name: catalystUser.last_name,
            })
            setTokenPair(tokens.access_token, tokens.refresh_token)
            setCurrentUser(await fetchCurrentUser())
          })(),
          CATALYST_BOOTSTRAP_TIMEOUT_MS,
        )
        clearCatalystExchangeFailure()
        clearAuthFailureReason()
      } catch (error) {
        clearTokens()
        setCurrentUser(null)
        markCatalystExchangeFailed()
        setAuthFailureReason("exchange_failed", extractApiErrorMessage(error, "Exchange request failed"))
      } finally {
        setIsSessionLoading(false)
      }
      return
    }
    try {
      const profile = await fetchCurrentUser()
      setCurrentUser(profile)
    } catch {
      clearTokens()
      setCurrentUser(null)
    } finally {
      setIsSessionLoading(false)
    }
  }, [])

  React.useEffect(() => {
    void loadProfileFromExistingSession()
  }, [loadProfileFromExistingSession])

  React.useEffect(() => {
    function handleSessionExpired() {
      setCurrentUser(null)
    }
    window.addEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired)
    return () => window.removeEventListener(AUTH_SESSION_EXPIRED_EVENT, handleSessionExpired)
  }, [])

  // Keeps `currentUser` in sync if the axios interceptor silently refreshes
  // (access token rotates) — currentUser identity doesn't change on refresh,
  // this just guards against a stale render if refresh happened during a
  // background tab / long-idle tab.
  React.useEffect(() => {
    return subscribeToTokenChanges(() => {
      if (!getRefreshToken()) setCurrentUser(null)
    })
  }, [])

  const refreshCurrentUser = React.useCallback(async () => {
    const profile = await fetchCurrentUser()
    setCurrentUser(profile)
  }, [])

  const endSession = React.useCallback(async () => {
    const refreshToken = getRefreshToken()
    clearTokens()
    setCurrentUser(null)
    clearCatalystExchangeFailure()
    markSignedOut()
    if (refreshToken) {
      try {
        await submitLogout(refreshToken)
      } catch {
        // Token is already cleared client-side regardless of server outcome.
      }
    }
    // Dropping our own tokens is not enough: the Catalyst/Zoho session outlives
    // them, and the bootstrap above would immediately trade it for a fresh
    // token pair — signing the user straight back in. Ending the Catalyst
    // session too is what makes sign-out actually stick. This navigates away,
    // so it must be the last thing we do.
    try {
      signOutOfCatalyst(`${window.location.origin}${import.meta.env.BASE_URL}login`)
    } catch {
      // No Catalyst SDK (local dev): there is no Catalyst session to end, so
      // clearing our own tokens above was already sufficient. The caller's
      // navigate("/login") still runs.
    }
  }, [])

  const value = React.useMemo<AuthContextValue>(
    () => ({
      currentUser,
      isSessionLoading,
      isAuthenticated: currentUser !== null,
      endSession,
      refreshCurrentUser,
    }),
    [currentUser, isSessionLoading, endSession, refreshCurrentUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within an AuthProvider")
  return context
}
