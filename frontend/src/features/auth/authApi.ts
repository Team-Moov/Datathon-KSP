import { httpClient } from "@/lib/api/httpClient"
import type { AuthenticatedUser, TokenPair } from "@/lib/types/api"
import type { PoliceRank } from "@/lib/types/permissions"

export async function fetchCurrentUser(): Promise<AuthenticatedUser> {
  const response = await httpClient.get<AuthenticatedUser>("/auth/me")
  return response.data
}

export async function submitLogout(refreshToken: string): Promise<void> {
  await httpClient.post("/auth/logout", { refresh_token: refreshToken })
}

/**
 * Trades a Catalyst-generated auth token (catalyst.auth.generateAuthToken())
 * for our own access/refresh token pair. See
 * backend/app/core/catalyst_request_auth.py for how the backend verifies
 * this — it never trusts the token itself, only what Catalyst's platform
 * validates it into on the way in.
 */
export async function exchangeCatalystIdentity(catalystToken: string): Promise<TokenPair> {
  const response = await httpClient.post<TokenPair>(
    "/auth/catalyst/exchange",
    {},
    { headers: { Authorization: catalystToken } },
  )
  return response.data
}

/** One-time role pick for a freshly Catalyst-provisioned account — see backend/app/api/v1/endpoints/auth.py. */
export async function selectRole(role: PoliceRank): Promise<AuthenticatedUser> {
  const response = await httpClient.post<AuthenticatedUser>("/auth/select-role", { role })
  return response.data
}
