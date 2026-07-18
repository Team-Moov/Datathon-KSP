import { httpClient } from "@/lib/api/httpClient"

export interface SuspiciousTransactionAlert {
  typology: string
  accounts_involved: string[]
  evidence_trail: Record<string, unknown>
  confidence: number
  recommended_action: string
  disclaimer: string
}

export async function detectStructuring(account: string, windowDays = 30): Promise<SuspiciousTransactionAlert | null> {
  const response = await httpClient.get<SuspiciousTransactionAlert | null>(`/financial/structuring/${account}`, {
    params: { window_days: windowDays },
  })
  return response.data
}

export async function detectFunnelAccount(account: string): Promise<SuspiciousTransactionAlert | null> {
  const response = await httpClient.get<SuspiciousTransactionAlert | null>(`/financial/funnel/${account}`)
  return response.data
}

export async function detectLayeringCycles(): Promise<SuspiciousTransactionAlert[]> {
  const response = await httpClient.get<SuspiciousTransactionAlert[]>("/financial/cycles")
  return response.data
}
