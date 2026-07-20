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
