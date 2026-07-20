import { httpClient } from "@/lib/api/httpClient"

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
