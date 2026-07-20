import { httpClient } from "@/lib/api/httpClient"

export interface RiskScoreResult {
  score_id: string
  person_id: string
  score: number
  model_version: string
  shap_decomposition: Record<string, number>
  human_reviewed: boolean
  computed_at: string
  disclaimer: string
}

export async function computePersonRiskScore(personId: string): Promise<RiskScoreResult> {
  const response = await httpClient.post<RiskScoreResult>(`/risk/${personId}/compute`)
  return response.data
}

export async function markRiskScoreReviewed(personId: string, scoreId: string) {
  const response = await httpClient.post(`/risk/${personId}/scores/${scoreId}/review`)
  return response.data
}
