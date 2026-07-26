/**
 * Thin wrapper around Zoho Catalyst's Web SDK (`window.catalyst`), loaded via
 * the script tags in index.html. Only functional once this app is served
 * through Catalyst Web Client Hosting — that's what makes
 * /__catalyst/sdk/init.js resolve and populate `window.catalyst`.
 * https://docs.catalyst.zoho.com/en/sdk/web/v4/overview
 * https://docs.catalyst.zoho.com/en/cloud-scale/help/authentication/native-catalyst-authentication/embedded-authentication/scripts-for-embedded/
 */

export interface CatalystProjectUser {
  zuid: string
  email_id: string
  first_name: string
  last_name: string
  role_details?: { role_name: string; role_id: string }
}

export interface CatalystSignInConfig {
  service_url?: string
  css_url?: string
  signin_providers_only?: boolean
}

interface CatalystAuthApi {
  signIn: (elementId: string, config?: CatalystSignInConfig) => void
  signOut: (redirectUrl: string) => void
  generateAuthToken: () => Promise<{ access_token: string }>
}

interface CatalystUserManagementApi {
  getCurrentProjectUser: () => Promise<{ content: CatalystProjectUser }>
}

interface CatalystGlobal {
  auth: CatalystAuthApi
  userManagement: CatalystUserManagementApi
}

declare global {
  interface Window {
    catalyst?: CatalystGlobal
    __catalystInitFailed?: boolean
  }
}

function getCatalyst(): CatalystGlobal {
  // window.catalyst can exist (the CDN script itself defines it) even when
  // /__catalyst/sdk/init.js 404'd — it just has no project config in that
  // case. __catalystInitFailed (set by that script tag's onerror in
  // index.html) is the real signal for "not served through Catalyst Web
  // Client Hosting", not window.catalyst's mere presence.
  if (!window.catalyst || window.__catalystInitFailed) {
    throw new Error(
      "Catalyst Web SDK is unavailable — this page must be served through Catalyst Web Client Hosting for /__catalyst/sdk/init.js to resolve.",
    )
  }
  return window.catalyst
}

/** Mounts the Catalyst login iFrame into the element with this id. */
export function mountCatalystSignIn(elementId: string, config?: CatalystSignInConfig): void {
  getCatalyst().auth.signIn(elementId, config)
}

export function signOutOfCatalyst(redirectUrl: string): void {
  getCatalyst().auth.signOut(redirectUrl)
}

/** Returns null rather than throwing when there's no active Catalyst session. */
export async function getCatalystProjectUser(): Promise<CatalystProjectUser | null> {
  try {
    const response = await getCatalyst().userManagement.getCurrentProjectUser()
    return response.content
  } catch {
    return null
  }
}

export async function generateCatalystAuthToken(): Promise<string> {
  const response = await getCatalyst().auth.generateAuthToken()
  return response.access_token
}
