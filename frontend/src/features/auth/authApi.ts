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

export interface CatalystIdentityPayload {
  email: string
  zuid?: string
  first_name?: string
  last_name?: string
}

/**
 * Trades a Catalyst identity for our own access/refresh token pair.
 * ⚠️ This identity is CLIENT-ASSERTED — the backend does not independently
 * re-verify it against Catalyst's servers on this deployment (GCP, not
 * AppSail). See backend/app/api/v1/endpoints/auth.py's exchange_catalyst_identity
 * docstring for the full tradeoff and why.
 */
export async function exchangeCatalystIdentity(identity: CatalystIdentityPayload): Promise<TokenPair> {
  const response = await httpClient.post<TokenPair>("/auth/catalyst/exchange", identity)
  return response.data
}

/** One-time role pick for a freshly Catalyst-provisioned account — see backend/app/api/v1/endpoints/auth.py. */
export async function selectRole(role: PoliceRank): Promise<AuthenticatedUser> {
  const response = await httpClient.post<AuthenticatedUser>("/auth/select-role", { role })
  return response.data
}
