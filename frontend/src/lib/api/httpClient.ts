import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios"

import {
  announceSessionExpired,
  getAccessToken,
  getRefreshToken,
  setTokenPair,
} from "./authTokenStore"
import type { ApiErrorPayload, TokenPair } from "@/lib/types/api"

export const httpClient = axios.create({
  baseURL: "/api/v1",
})

httpClient.interceptors.request.use((config) => {
  const accessToken = getAccessToken()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
})

interface RetriableRequestConfig extends InternalAxiosRequestConfig {
  _hasRetriedAfterRefresh?: boolean
}

let pendingRefreshRequest: Promise<TokenPair> | null = null

async function refreshAccessToken(): Promise<TokenPair> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) {
    throw new Error("No refresh token available")
  }
  const response = await axios.post<TokenPair>("/api/v1/auth/refresh", { refresh_token: refreshToken })
  setTokenPair(response.data.access_token, response.data.refresh_token)
  return response.data
}

httpClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiErrorPayload>) => {
    const originalRequest = error.config as RetriableRequestConfig | undefined
    const isUnauthorized = error.response?.status === 401
    // Only the refresh call itself (and the credential/OTP steps, where a 401
    // means "wrong password/code" rather than "session expired") are excluded
    // from the retry loop. /auth/me is a normal protected endpoint that must
    // still go through silent refresh on page load — a blanket "/auth/" prefix
    // check here previously swallowed it too, breaking session restore on
    // every hard reload even with a perfectly valid refresh token.
    const skipRefreshUrls = ["/auth/refresh", "/auth/token", "/auth/mfa/verify", "/auth/mfa/resend"]
    const isRefreshExemptEndpoint = skipRefreshUrls.some((path) => originalRequest?.url?.startsWith(path))

    if (!isUnauthorized || !originalRequest || isRefreshExemptEndpoint || originalRequest._hasRetriedAfterRefresh) {
      return Promise.reject(error)
    }

    originalRequest._hasRetriedAfterRefresh = true
    try {
      pendingRefreshRequest ??= refreshAccessToken().finally(() => {
        pendingRefreshRequest = null
      })
      const refreshed = await pendingRefreshRequest
      originalRequest.headers.Authorization = `Bearer ${refreshed.access_token}`
      return httpClient(originalRequest)
    } catch {
      announceSessionExpired()
      return Promise.reject(error)
    }
  },
)

export function extractApiErrorMessage(error: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError<ApiErrorPayload>(error)) {
    return error.response?.data?.detail ?? error.response?.data?.message ?? error.message ?? fallback
  }
  if (error instanceof Error) return error.message
  return fallback
}
