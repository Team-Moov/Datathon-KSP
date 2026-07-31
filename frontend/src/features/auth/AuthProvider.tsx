import * as React from "react"

import {
  AUTH_SESSION_EXPIRED_EVENT,
  clearTokens,
  getRefreshToken,
  setTokenPair,
  subscribeToTokenChanges,
} from "@/lib/api/authTokenStore"
import type { AuthenticatedUser, TokenPair } from "@/lib/types/api"
import { fetchCurrentUser, submitLogout } from "./authApi"

interface AuthContextValue {
  currentUser: AuthenticatedUser | null
  isSessionLoading: boolean
  isAuthenticated: boolean
  applyTokenPair: (tokens: TokenPair) => Promise<void>
  endSession: () => Promise<void>
  /** Re-fetches /auth/me without touching tokens — used after POST /auth/select-role. */
  refreshCurrentUser: () => Promise<void>
}

const AuthContext = React.createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = React.useState<AuthenticatedUser | null>(null)
  const [isSessionLoading, setIsSessionLoading] = React.useState(true)

  const loadProfileFromExistingSession = React.useCallback(async () => {
    if (!getRefreshToken()) {
      setCurrentUser(null)
      setIsSessionLoading(false)
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

  const applyTokenPair = React.useCallback(async (tokens: TokenPair) => {
    setTokenPair(tokens.access_token, tokens.refresh_token)
    const profile = await fetchCurrentUser()
    setCurrentUser(profile)
  }, [])

  const refreshCurrentUser = React.useCallback(async () => {
    const profile = await fetchCurrentUser()
    setCurrentUser(profile)
  }, [])

  const endSession = React.useCallback(async () => {
    const refreshToken = getRefreshToken()
    clearTokens()
    setCurrentUser(null)
    if (refreshToken) {
      try {
        await submitLogout(refreshToken)
      } catch {
        // Token is already cleared client-side regardless of server outcome.
      }
    }
  }, [])

  const value = React.useMemo<AuthContextValue>(
    () => ({
      currentUser,
      isSessionLoading,
      isAuthenticated: currentUser !== null,
      applyTokenPair,
      endSession,
      refreshCurrentUser,
    }),
    [currentUser, isSessionLoading, applyTokenPair, endSession, refreshCurrentUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = React.useContext(AuthContext)
  if (!context) throw new Error("useAuth must be used within an AuthProvider")
  return context
}
