import { httpClient } from "@/lib/api/httpClient"
import type { CrimeHeadOption } from "@/components/charts/CrimeHeadListCard"
import type { TemporalTrendsData } from "@/components/charts/TemporalTrendsChart"
import type { SurveillancePrioritiesData } from "@/components/charts/SurveillancePriorityList"
import type { MoLinkageCluster } from "@/components/charts/MoLinkageList"
import type { DistrictOption } from "@/features/socio/socioApi"

export interface HotspotForecastCell {
  lat_center: number
  lng_center: number
  predicted_rate: number
  background_component: number
  near_repeat_component: number
  forecast_date: string
}

export interface HotspotForecastParams {
  districtId: number
  crimeHeadId: number
  targetDate: string
  stressIndex?: number
}

export async function fetchHotspotForecast(params: HotspotForecastParams): Promise<HotspotForecastCell[]> {
  const response = await httpClient.get<HotspotForecastCell[]>("/trends/hotspots", {
    params: {
      district_id: params.districtId,
      crime_head_id: params.crimeHeadId,
      target_date: params.targetDate,
      stress_index: params.stressIndex,
    },
  })
  return response.data
}

export async function fetchTrendsDistricts(): Promise<DistrictOption[]> {
  const response = await httpClient.get<DistrictOption[]>("/trends/districts")
  return response.data
}

export async function fetchCrimeHeads(): Promise<CrimeHeadOption[]> {
  const response = await httpClient.get<CrimeHeadOption[]>("/trends/crime-heads")
  return response.data
}

export async function fetchTemporalTrends(districtId: number, crimeHeadId?: number): Promise<TemporalTrendsData> {
  const response = await httpClient.get<TemporalTrendsData>("/trends/temporal", {
    params: { district_id: districtId, crime_head_id: crimeHeadId },
  })
  return response.data
}

export async function fetchSurveillancePriorities(params: {
  districtId: number
  crimeHeadId: number
  targetDate: string
  topN?: number
  stressIndex?: number
}): Promise<SurveillancePrioritiesData> {
  const response = await httpClient.get<SurveillancePrioritiesData>("/trends/surveillance-priorities", {
    params: {
      district_id: params.districtId,
      crime_head_id: params.crimeHeadId,
      target_date: params.targetDate,
      top_n: params.topN,
      stress_index: params.stressIndex,
    },
  })
  return response.data
}

export async function fetchMoLinkageClusters(crimeHeadId: number, minSimilarity = 0.7): Promise<MoLinkageCluster[]> {
  const response = await httpClient.get<MoLinkageCluster[]>(`/trends/mo-linkage/${crimeHeadId}`, {
    params: { min_similarity: minSimilarity },
  })
  return response.data
}
