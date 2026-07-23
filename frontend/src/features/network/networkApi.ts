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

export interface GraphSubsetFilters {
  nodeLabels?: string[]
  edgeTypes?: string[]
  districtId?: number
  crimeNoContains?: string
  dateFrom?: string
  dateTo?: string
  centerPersonId?: string
  depth?: number
  limit?: number
}

export async function fetchGraphSubset(filters: GraphSubsetFilters): Promise<EgoNetworkResult> {
  // Built as URLSearchParams explicitly (repeated key=value per array entry)
  // rather than relying on axios's array-param serialization, since FastAPI's
  // List[str] Query param expects the repeated-key form, not bracket/indexed
  // notation some axios configs default to.
  const params = new URLSearchParams()
  filters.nodeLabels?.forEach((label) => params.append("node_labels", label))
  filters.edgeTypes?.forEach((type) => params.append("edge_types", type))
  if (filters.districtId !== undefined) params.set("district_id", String(filters.districtId))
  if (filters.crimeNoContains) params.set("crime_no_contains", filters.crimeNoContains)
  if (filters.dateFrom) params.set("date_from", filters.dateFrom)
  if (filters.dateTo) params.set("date_to", filters.dateTo)
  if (filters.centerPersonId) params.set("center_person_id", filters.centerPersonId)
  if (filters.depth !== undefined) params.set("depth", String(filters.depth))
  if (filters.limit !== undefined) params.set("limit", String(filters.limit))

  const response = await httpClient.get<EgoNetworkResult>("/network/query", { params })
  return response.data
}
