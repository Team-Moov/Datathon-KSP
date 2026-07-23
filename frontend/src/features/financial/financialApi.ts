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

export async function detectOrganizedClusters(flaggedAccounts: string[]): Promise<SuspiciousTransactionAlert[]> {
  const response = await httpClient.post<SuspiciousTransactionAlert[]>("/financial/organized-clusters", {
    flagged_accounts: flaggedAccounts,
  })
  return response.data
}

export async function runFullScan(accounts: string[]): Promise<SuspiciousTransactionAlert[]> {
  const response = await httpClient.post<SuspiciousTransactionAlert[]>("/financial/scan", { accounts })
  return response.data
}

export interface PersonAccount {
  account: string
  txn_count: number
  flagged: boolean
}

/** Accounts appearing in a person's linked transactions — the bridge that lets the
 * financial workflow start from a person instead of an opaque account string. */
export async function fetchPersonAccounts(personId: string): Promise<PersonAccount[]> {
  const response = await httpClient.get<PersonAccount[]>("/financial/accounts", { params: { person_id: personId } })
  return response.data
}
