import { httpClient } from "@/lib/api/httpClient"

export interface GraphNode {
  id: string
  labels: string[]
  properties: Record<string, unknown>
}

export interface GraphEdge {
  id: string
  type: string
  from: string
  to: string
  properties: Record<string, unknown>
}

export interface EgoNetworkResult {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface PredictedLink {
  predicted_person_id: string
  name: string
  confidence: number
  source_tool: string
}

export interface MultiJurisdictionOffender {
  person_id: string
  name: string
  jurisdiction_count: number
  units: number[]
}

export async function fetchEgoNetwork(personId: string, depth = 2): Promise<EgoNetworkResult> {
  const response = await httpClient.get<EgoNetworkResult>(`/network/ego/${personId}`, { params: { depth } })
  return response.data
}

export async function fetchPredictedLinks(personId: string, topK = 10): Promise<PredictedLink[]> {
  const response = await httpClient.get<PredictedLink[]>(`/network/predicted-links/${personId}`, {
    params: { top_k: topK },
  })
  return response.data
}

export async function fetchMultiJurisdictionOffenders(): Promise<MultiJurisdictionOffender[]> {
  const response = await httpClient.get<MultiJurisdictionOffender[]>("/network/multi-jurisdiction")
  return response.data
}
