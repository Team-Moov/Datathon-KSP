import { httpClient } from "@/lib/api/httpClient"

export interface ModelFairness {
  protected_attributes_used: boolean
  protected_attributes: string[]
  audit: string
}

export interface ModelCard {
  model_version: string
  name: string
  family: string
  task: string
  capability: string
  primary_metric: { label: string; value: number }
  metrics: Record<string, number | string>
  feature_importance: Record<string, number> | null
  feature_importance_method?: string
  training: Record<string, number | string>
  fairness: ModelFairness
}

export async function fetchModelCards() {
  const response = await httpClient.get<ModelCard[]>("/models/")
  return response.data
}
