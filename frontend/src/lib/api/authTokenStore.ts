/**
 * Plain (non-React) token store — the axios interceptor needs to read/write
 * tokens outside of any component tree, and AuthProvider subscribes here to
 * stay in sync when the interceptor silently refreshes or force-logs-out.
 * Access token lives in memory only; refresh token persists to localStorage
 * so a page reload doesn't require re-entering the password + OTP.
 */

const REFRESH_TOKEN_STORAGE_KEY = "ksp.refreshToken"

let inMemoryAccessToken: string | null = null
type TokenChangeListener = () => void
const listeners = new Set<TokenChangeListener>()

function notifyListeners() {
  listeners.forEach((listener) => listener())
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY)
}

export function setTokenPair(accessToken: string, refreshToken: string): void {
  inMemoryAccessToken = accessToken
  localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, refreshToken)
  notifyListeners()
}

export function clearTokens(): void {
  inMemoryAccessToken = null
  localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY)
  notifyListeners()
}

export function subscribeToTokenChanges(listener: TokenChangeListener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export const AUTH_SESSION_EXPIRED_EVENT = "ksp:auth-session-expired"

export function announceSessionExpired(): void {
  clearTokens()
  window.dispatchEvent(new Event(AUTH_SESSION_EXPIRED_EVENT))
}
