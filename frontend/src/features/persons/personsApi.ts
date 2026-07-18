import { httpClient } from "@/lib/api/httpClient"
import type { PersonSummary } from "@/lib/types/api"

export async function searchPersonsByName(query: string): Promise<PersonSummary[]> {
  const response = await httpClient.get<PersonSummary[]>("/persons/search", { params: { q: query } })
  return response.data
}

export async function fetchPersonById(personId: string): Promise<PersonSummary> {
  const response = await httpClient.get<PersonSummary>(`/persons/${personId}`)
  return response.data
}

export async function submitPersonVerification(personId: string, version: number, reason?: string) {
  const response = await httpClient.post<PersonSummary>(`/persons/${personId}/verify`, { version, reason })
  return response.data
}
