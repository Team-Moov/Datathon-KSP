import { httpClient } from "@/lib/api/httpClient"
import type { AuthenticatedUser, LoginResult, TokenPair } from "@/lib/types/api"

export async function submitLoginCredentials(email: string, password: string): Promise<LoginResult> {
  const form = new URLSearchParams()
  form.set("username", email)
  form.set("password", password)
  const response = await httpClient.post<LoginResult>("/auth/token", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  })
  return response.data
}

export async function submitMfaCode(challengeId: string, code: string): Promise<TokenPair> {
  const response = await httpClient.post<TokenPair>("/auth/mfa/verify", { challenge_id: challengeId, code })
  return response.data
}

export async function requestMfaResend(challengeId: string) {
  const response = await httpClient.post("/auth/mfa/resend", { challenge_id: challengeId })
  return response.data
}

export async function fetchCurrentUser(): Promise<AuthenticatedUser> {
  const response = await httpClient.get<AuthenticatedUser>("/auth/me")
  return response.data
}

export async function submitLogout(refreshToken: string): Promise<void> {
  await httpClient.post("/auth/logout", { refresh_token: refreshToken })
}
