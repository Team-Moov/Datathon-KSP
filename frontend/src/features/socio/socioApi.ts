import { httpClient } from "@/lib/api/httpClient"

export interface SocioIndicatorPoint {
  year: number
  literacy_rate: number | null
  unemployment_rate: number | null
  urbanization_pct: number | null
  sex_ratio: number | null
  composite_stress_index: number | null
}

export interface CrimeStatPoint {
  year: number
  crime_head_id: number
  count: number
  chi_weighted_count: number | null
}

export interface GwrRun {
  model_version: string
  run_timestamp: string
  data_version: string
  gwr_coefficients: Record<string, number>
  composite_score: number | null
}

export interface GwrDistrictPoint {
  district_id: number
  district_name: string
  gwr_coefficients: Record<string, number>
  composite_score: number | null
  lat: number | null
  lon: number | null
}

export async function fetchSocioIndicators(districtId: number, yearFrom?: number, yearTo?: number) {
  const response = await httpClient.get<SocioIndicatorPoint[]>(`/socio/indicators/${districtId}`, {
    params: { year_from: yearFrom, year_to: yearTo },
  })
  return response.data
}

export async function fetchCrimeStats(districtId: number, year?: number, crimeHeadId?: number) {
  const response = await httpClient.get<CrimeStatPoint[]>(`/socio/crime-stats/${districtId}`, {
    params: { year, crime_head_id: crimeHeadId },
  })
  return response.data
}

export async function fetchGwrOutputs(districtId: number) {
  const response = await httpClient.get<GwrRun[]>(`/socio/gwr/${districtId}`)
  return response.data
}

export async function fetchGwrMap() {
  const response = await httpClient.get<GwrDistrictPoint[]>("/socio/gwr-map")
  return response.data
}
