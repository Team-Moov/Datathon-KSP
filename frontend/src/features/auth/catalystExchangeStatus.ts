/**
 * Records that a Catalyst identity exchange was attempted and failed.
 *
 * This exists purely to break a redirect loop. Catalyst redirects a user who
 * already holds a Zoho session straight back into the app, so if the exchange
 * fails (backend unreachable, 5xx, misconfigured VITE_API_BASE_URL) the guard
 * bounces to /login, LoginPage remounts the sign-in iFrame, Catalyst redirects
 * again — forever, as a full page reload each time. Nothing in React state
 * survives that reload, so the flag lives in sessionStorage: it outlives the
 * reload but not the tab, so closing and reopening is a natural retry.
 */

const FAILURE_KEY = "catalystExchangeFailed"
const REASON_KEY = "catalystAuthFailureReason"

/**
 * Why the Catalyst bootstrap did not produce a session.
 *
 * These were all reported as "No active Catalyst session", which is only
 * correct for `no_project_user` and actively misleading for the other two: a
 * backend that rejected the exchange looks identical to never having signed
 * in. Recording the reason is what makes the three distinguishable on screen
 * instead of requiring a console dive.
 */
export type CatalystAuthFailureReason =
  /** getCurrentProjectUser() returned nothing: signed in to Zoho, but not a project user here. */
  | "no_project_user"
  /** The identity was read, but POST /auth/catalyst/exchange failed. */
  | "exchange_failed"
  /** Adoption was deliberately skipped after a sign-out. */
  | "signed_out"

export function setAuthFailureReason(reason: CatalystAuthFailureReason, detail?: string): void {
  try {
    sessionStorage.setItem(REASON_KEY, detail ? `${reason}|${detail}` : reason)
  } catch {
    /* Diagnostics are best-effort. */
  }
}

export function getAuthFailureReason(): { reason: CatalystAuthFailureReason; detail?: string } | null {
  try {
    const raw = sessionStorage.getItem(REASON_KEY)
    if (!raw) return null
    const [reason, ...rest] = raw.split("|")
    return { reason: reason as CatalystAuthFailureReason, detail: rest.join("|") || undefined }
  } catch {
    return null
  }
}

export function clearAuthFailureReason(): void {
  try {
    sessionStorage.removeItem(REASON_KEY)
  } catch {
    /* Diagnostics are best-effort. */
  }
}

// sessionStorage throws rather than returning null in some embedded/partitioned
// contexts. A storage failure must never be what breaks sign-in, so every
// access degrades to "no failure recorded" and the normal flow proceeds.
export function markCatalystExchangeFailed(): void {
  try {
    sessionStorage.setItem(FAILURE_KEY, "1")
  } catch {
    /* Loop protection is best-effort; sign-in still works without it. */
  }
}

export function hasCatalystExchangeFailed(): boolean {
  try {
    return sessionStorage.getItem(FAILURE_KEY) === "1"
  } catch {
    return false
  }
}

export function clearCatalystExchangeFailure(): void {
  try {
    sessionStorage.removeItem(FAILURE_KEY)
  } catch {
    /* See above. */
  }
}

/**
 * Records that the user signed out deliberately.
 *
 * Ending the Catalyst session is not enough to make sign-out stick. The
 * browser still holds the Zoho account SSO cookie, so the embedded sign-in
 * iFrame re-authenticates the moment it mounts, with no interaction, and the
 * user lands straight back in the app. Signing out of Zoho account-wide is not
 * ours to do, so instead we stop auto-mounting the iFrame: after a deliberate
 * sign-out the login screen waits for an explicit "Sign in" click. That holds
 * regardless of what the SSO cookie does.
 */
const SIGNED_OUT_KEY = "catalystSignedOut"

export function markSignedOut(): void {
  try {
    sessionStorage.setItem(SIGNED_OUT_KEY, "1")
  } catch {
    /* Best effort, as above. */
  }
}

export function hasSignedOut(): boolean {
  try {
    return sessionStorage.getItem(SIGNED_OUT_KEY) === "1"
  } catch {
    return false
  }
}

export function clearSignedOut(): void {
  try {
    sessionStorage.removeItem(SIGNED_OUT_KEY)
  } catch {
    /* Best effort, as above. */
  }
}
