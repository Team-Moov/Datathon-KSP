import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import {
  BarChart3,
  Building2,
  Compass,
  Map,
  Sparkles,
  TrendingUp,
  UsersRound,
} from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"

import {
  fetchDistricts,
  fetchGwrMap,
  fetchGwrOutputs,
  fetchPolicyRecommendations,
  fetchSocioCorrelations,
  fetchSocioIndicators,
  fetchUrbanizationImpact,
  fetchVictimDemographics,
} from "./socioApi"

import { PolicyRecommendationsCard } from "@/components/charts/PolicyRecommendationsCard"
import { SocioCorrelationMatrix } from "@/components/charts/SocioCorrelationMatrix"
import { UrbanizationImpactChart } from "@/components/charts/UrbanizationImpactChart"
import { VictimDemographicsChart } from "@/components/charts/VictimDemographicsChart"

const TrendLineChart = React.lazy(() =>
  import("@/components/charts/TrendLineChart").then((m) => ({ default: m.TrendLineChart }))
)
const GwrCoefficientsList = React.lazy(() =>
  import("@/components/charts/GwrCoefficientsList").then((m) => ({ default: m.GwrCoefficientsList }))
)
const GwrCentroidMap = React.lazy(() =>
  import("@/components/charts/GwrCentroidMap").then((m) => ({ default: m.GwrCentroidMap }))
)

type ActiveTab = "overview" | "demographics" | "correlations" | "gwr" | "urbanization" | "policy"

function SocioInsightsPage() {
  const [districtId, setDistrictId] = React.useState<string>("1")
  const [activeTab, setActiveTab] = React.useState<ActiveTab>("overview")

  const districtsQuery = useQuery({
    queryKey: ["socio-districts"],
    queryFn: fetchDistricts,
  })

  // Auto-select first district when districts load if current selection isn't found
  React.useEffect(() => {
    if (districtsQuery.data && districtsQuery.data.length > 0) {
      const exists = districtsQuery.data.some((d) => String(d.district_id) === districtId)
      if (!exists) {
        setDistrictId(String(districtsQuery.data[0].district_id))
      }
    }
  }, [districtsQuery.data, districtId])

  const selectedDistrict = districtsQuery.data?.find((d) => String(d.district_id) === districtId)

  const indicatorsQuery = useQuery({
    queryKey: ["socio-indicators", districtId],
    queryFn: () => fetchSocioIndicators(Number(districtId)),
    enabled: districtId.trim().length > 0,
  })

  const gwrQuery = useQuery({
    queryKey: ["gwr-outputs", districtId],
    queryFn: () => fetchGwrOutputs(Number(districtId)),
    enabled: districtId.trim().length > 0,
  })

  const gwrMapQuery = useQuery({
    queryKey: ["gwr-map"],
    queryFn: fetchGwrMap,
  })

  const correlationsQuery = useQuery({
    queryKey: ["socio-correlations"],
    queryFn: fetchSocioCorrelations,
  })

  const victimDemographicsQuery = useQuery({
    queryKey: ["victim-demographics", districtId],
    queryFn: () => fetchVictimDemographics(Number(districtId)),
  })

  const urbanizationQuery = useQuery({
    queryKey: ["urbanization-impact"],
    queryFn: fetchUrbanizationImpact,
  })

  const policyQuery = useQuery({
    queryKey: ["policy-recommendations", districtId],
    queryFn: () => fetchPolicyRecommendations(Number(districtId)),
    enabled: districtId.trim().length > 0,
  })

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 p-6 rounded-2xl text-white shadow-lg">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <UsersRound className="w-6 h-6 text-indigo-300" />
            <h1 className="text-xl font-bold tracking-tight">Sociological Crime Insights & Policy Platform</h1>
          </div>
          <p className="text-xs text-indigo-200/90 max-w-2xl leading-relaxed">
            Place-level criminological analytics grounded in Social Disorganization Theory (Shaw & McKay). District aggregate indicators are strictly firewalled from individual person records.
          </p>
        </div>

        {/* District Selector Control */}
        <div className="bg-white/10 backdrop-blur-md border border-white/20 p-3 rounded-xl flex items-center gap-3">
          <Compass className="w-5 h-5 text-indigo-300 shrink-0" />
          <div className="space-y-0.5">
            <label htmlFor="district-select" className="text-[10px] font-semibold uppercase tracking-wider text-indigo-200">
              Target District
            </label>
            <select
              id="district-select"
              value={districtId}
              onChange={(e) => setDistrictId(e.target.value)}
              className="bg-zinc-900/90 text-white text-xs font-semibold rounded-md px-3 py-1.5 border border-white/20 focus:outline-none focus:ring-2 focus:ring-indigo-400"
            >
              {districtsQuery.data && districtsQuery.data.length > 0 ? (
                districtsQuery.data.map((d) => (
                  <option key={d.district_id} value={String(d.district_id)}>
                    {d.name} ({d.code})
                  </option>
                ))
              ) : (
                <option value="1">Bengaluru Urban</option>
              )}
            </select>
          </div>
        </div>
      </div>

      {/* District KPI Summary Header */}
      {selectedDistrict && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm space-y-1">
            <span className="text-[11px] font-medium text-zinc-500">Composite Stress Score</span>
            <div className="text-lg font-bold text-indigo-600 dark:text-indigo-400">
              {selectedDistrict.composite_stress_index !== null ? selectedDistrict.composite_stress_index.toFixed(2) : "No data"}
            </div>
          </div>
          <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm space-y-1">
            <span className="text-[11px] font-medium text-zinc-500">Literacy Rate</span>
            <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
              {selectedDistrict.literacy_rate !== null ? `${selectedDistrict.literacy_rate.toFixed(1)}%` : "No data"}
            </div>
          </div>
          <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm space-y-1">
            <span className="text-[11px] font-medium text-zinc-500">Unemployment Rate</span>
            <div className="text-lg font-bold text-amber-600 dark:text-amber-400">
              {selectedDistrict.unemployment_rate !== null ? `${selectedDistrict.unemployment_rate.toFixed(1)}%` : "No data"}
            </div>
          </div>
          <div className="p-3.5 rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm space-y-1">
            <span className="text-[11px] font-medium text-zinc-500">Urbanization Level</span>
            <div className="text-lg font-bold text-blue-600 dark:text-blue-400">
              {selectedDistrict.urbanization_pct !== null ? `${selectedDistrict.urbanization_pct.toFixed(1)}%` : "No data"}
            </div>
          </div>
        </div>
      )}

      {/* Analytics Tabs Navigation */}
      <div className="flex overflow-x-auto gap-1 border-b border-zinc-200 dark:border-zinc-800 pb-2">
        <button
          onClick={() => setActiveTab("overview")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "overview"
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          <span>Socio-Economic Trends</span>
        </button>

        <button
          onClick={() => setActiveTab("demographics")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "demographics"
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <UsersRound className="w-3.5 h-3.5" />
          <span>Victim Demographics</span>
        </button>

        <button
          onClick={() => setActiveTab("correlations")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "correlations"
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>Harm Correlation Matrix</span>
        </button>

        <button
          onClick={() => setActiveTab("gwr")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "gwr"
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <Map className="w-3.5 h-3.5" />
          <span>GWR Spatial Model</span>
        </button>

        <button
          onClick={() => setActiveTab("urbanization")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "urbanization"
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <Building2 className="w-3.5 h-3.5" />
          <span>Urban Growth Velocity</span>
        </button>

        <button
          onClick={() => setActiveTab("policy")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "policy"
              ? "bg-indigo-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>Policy Diagnostic</span>
        </button>
      </div>

      {/* Tab Content Display */}
      <div className="space-y-6">
        {/* Tab 1: Socio-Economic Trends */}
        {activeTab === "overview" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
                District Socio-Economic Time Series
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {indicatorsQuery.isLoading ? (
                <LoadingSkeleton variant="card" rows={1} />
              ) : indicatorsQuery.isError ? (
                <ErrorState message={extractApiErrorMessage(indicatorsQuery.error)} onRetry={() => void indicatorsQuery.refetch()} />
              ) : !indicatorsQuery.data || indicatorsQuery.data.length === 0 ? (
                <EmptyState icon={UsersRound} title="No indicator data available for this district" />
              ) : (
                <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                  <TrendLineChart
                    data={indicatorsQuery.data}
                    xKey="year"
                    seriesKeys={[
                      { key: "literacy_rate", label: "Literacy Rate (%)", color: "#5f6299" },
                      { key: "unemployment_rate", label: "Unemployment Rate (%)", color: "#b1503f" },
                      { key: "composite_stress_index", label: "Composite Stress Index", color: "#b8863f" },
                    ]}
                  />
                </React.Suspense>
              )}
            </CardContent>
          </Card>
        )}

        {/* Tab 2: Victim Demographics */}
        {activeTab === "demographics" && (
          <div>
            {victimDemographicsQuery.isLoading ? (
              <LoadingSkeleton variant="card" rows={2} />
            ) : victimDemographicsQuery.isError ? (
              <ErrorState message={extractApiErrorMessage(victimDemographicsQuery.error)} onRetry={() => void victimDemographicsQuery.refetch()} />
            ) : victimDemographicsQuery.data && victimDemographicsQuery.data.status === "insufficient_data" ? (
              <EmptyState icon={UsersRound} title="No victim-role case data for this scope" description={victimDemographicsQuery.data.police_resource_recommendation} />
            ) : victimDemographicsQuery.data ? (
              <VictimDemographicsChart data={victimDemographicsQuery.data} />
            ) : null}
          </div>
        )}

        {/* Tab 3: Harm Correlation Matrix */}
        {activeTab === "correlations" && (
          <div>
            {correlationsQuery.isLoading ? (
              <LoadingSkeleton variant="card" rows={2} />
            ) : correlationsQuery.isError ? (
              <ErrorState message={extractApiErrorMessage(correlationsQuery.error)} onRetry={() => void correlationsQuery.refetch()} />
            ) : correlationsQuery.data && correlationsQuery.data.status === "insufficient_data" ? (
              <EmptyState icon={BarChart3} title="Not enough data for a correlation matrix" description={correlationsQuery.data.key_takeaway} />
            ) : correlationsQuery.data ? (
              <SocioCorrelationMatrix data={correlationsQuery.data} />
            ) : null}
          </div>
        )}

        {/* Tab 4: GWR Spatial Model */}
        {activeTab === "gwr" && (
          <div className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
                  Geographically Weighted Regression — District Coefficients
                </CardTitle>
              </CardHeader>
              <CardContent>
                {gwrQuery.isLoading ? (
                  <LoadingSkeleton variant="card" rows={1} />
                ) : gwrQuery.isError ? (
                  <ErrorState message={extractApiErrorMessage(gwrQuery.error)} onRetry={() => void gwrQuery.refetch()} />
                ) : !gwrQuery.data || gwrQuery.data.length === 0 ? (
                  <EmptyState title="No GWR runs available for this district" description="Execute GWR compute pipeline to generate versioned coefficient matrices." />
                ) : (
                  <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                    <GwrCoefficientsList runs={gwrQuery.data} />
                  </React.Suspense>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
                  Statewide GWR Coefficient Heatmap Centroids
                </CardTitle>
              </CardHeader>
              <CardContent>
                {gwrMapQuery.isLoading ? (
                  <LoadingSkeleton variant="card" rows={1} />
                ) : gwrMapQuery.isError ? (
                  <ErrorState message={extractApiErrorMessage(gwrMapQuery.error)} onRetry={() => void gwrMapQuery.refetch()} />
                ) : !gwrMapQuery.data || gwrMapQuery.data.length === 0 ? (
                  <EmptyState icon={Map} title="No GWR map data available" description="Run GWR computation to populate district centroids." />
                ) : (
                  <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                    <GwrCentroidMap points={gwrMapQuery.data} />
                  </React.Suspense>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Tab 5: Urban Growth Velocity */}
        {activeTab === "urbanization" && (
          <div>
            {urbanizationQuery.isLoading ? (
              <LoadingSkeleton variant="card" rows={2} />
            ) : urbanizationQuery.isError ? (
              <ErrorState message={extractApiErrorMessage(urbanizationQuery.error)} onRetry={() => void urbanizationQuery.refetch()} />
            ) : !urbanizationQuery.data || urbanizationQuery.data.length === 0 ? (
              <EmptyState icon={Building2} title="Not enough multi-year data" description="At least two years of urbanization indicator data per district are needed to compute a growth trend." />
            ) : (
              <UrbanizationImpactChart data={urbanizationQuery.data} />
            )}
          </div>
        )}

        {/* Tab 6: Policy Diagnostic */}
        {activeTab === "policy" && (
          <div>
            {policyQuery.isLoading ? (
              <LoadingSkeleton variant="card" rows={2} />
            ) : policyQuery.isError ? (
              <ErrorState message={extractApiErrorMessage(policyQuery.error)} onRetry={() => void policyQuery.refetch()} />
            ) : policyQuery.data ? (
              <PolicyRecommendationsCard data={policyQuery.data} />
            ) : null}
          </div>
        )}
      </div>
    </div>
  )
}

export { SocioInsightsPage }
