import type { PoliceStaffingData } from "@/components/charts/PoliceStaffingCard"
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

export interface DistrictOption {
  district_id: number
  name: string
  code: string
  lat: number | null
  lon: number | null
  composite_stress_index: number | null
  literacy_rate: number | null
  unemployment_rate: number | null
  urbanization_pct: number | null
  sex_ratio: number | null
}

export interface SocioCorrelationItem {
  indicator: string
  r_raw: number
  r_chi: number
  p_val_chi: number
  significance: string
}

export interface SocioCorrelationResponse {
  status: "ok" | "insufficient_data"
  sample_size: number
  correlations: SocioCorrelationItem[]
  chi_vs_raw_delta: string | null
  key_takeaway: string
}

export interface AgeGroupCohort {
  cohort: string
  theft_pct: number
  cyber_pct: number
  violent_pct: number
  overall_pct: number
}

export interface GenderDistributionCategory {
  category: string
  male_pct: number
  female_pct: number
}

export interface SocioEconomicVulnerability {
  stratum: string
  vulnerability_score: number
  primary_risk: string
}

export interface VictimDemographicsData {
  status: "ok" | "insufficient_data"
  age_groups: AgeGroupCohort[]
  gender_distribution: GenderDistributionCategory[]
  socio_economic_vulnerability: SocioEconomicVulnerability[]
  police_resource_recommendation: string
}

export interface UrbanizationImpactItem {
  district_name: string
  phase: string
  urbanization_growth_pct: number
  crime_velocity_change: string
  primary_crime_head: string
  social_mechanism: string
  status: string
}

export interface PolicyRecommendationItem {
  domain: string
  priority: string
  theory_grounding: string
  action: string
  expected_impact: string
}

export interface PolicyRecommendationsResponse {
  district_id: number
  district_name: string
  stress_index: number
  risk_level: string
  indicators_summary: Record<string, string>
  recommendations: PolicyRecommendationItem[]
  criminological_note: string
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

export async function fetchDistricts() {
  const response = await httpClient.get<DistrictOption[]>("/socio/districts")
  return response.data
}

export async function fetchSocioCorrelations() {
  const response = await httpClient.get<SocioCorrelationResponse>("/socio/correlations")
  return response.data
}

export async function fetchVictimDemographics(districtId?: number) {
  const response = await httpClient.get<VictimDemographicsData>("/socio/demographics/victims", {
    params: { district_id: districtId },
  })
  return response.data
}

export async function fetchUrbanizationImpact() {
  const response = await httpClient.get<UrbanizationImpactItem[]>("/socio/urbanization-impact")
  return response.data
}

export async function fetchPolicyRecommendations(districtId: number) {
  const response = await httpClient.get<PolicyRecommendationsResponse>(`/socio/policy-recommendations/${districtId}`)
  return response.data
}


export async function fetchPoliceStaffing(districtId: number) {
  const response = await httpClient.get<PoliceStaffingData>(`/socio/calculate-staffing/${districtId}`)
  return response.data
}
