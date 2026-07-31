import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
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
import { MetricWithInfo } from "@/components/MetricWithInfo"
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
  const { t } = useTranslation()
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
      <div className="space-y-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <UsersRound className="w-6 h-6 text-accent-600 dark:text-accent-300" />
            <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">{t("socio.title")}</h1>
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 max-w-2xl leading-relaxed">
            {t("socio.description")}
          </p>
        </div>

        {/* District Selector Control */}
        <div className="flat-surface border border-zinc-200 dark:border-zinc-800 p-3 rounded-lg flex items-center gap-3">
          <Compass className="w-5 h-5 text-accent-600 dark:text-accent-300 shrink-0" />
          <div className="space-y-0.5">
            <label htmlFor="district-select" className="text-[10px] font-semibold uppercase tracking-wider text-zinc-600 dark:text-zinc-400">
              {t("common.targetDistrict")}
            </label>
            <select
              id="district-select"
              value={districtId}
              onChange={(e) => setDistrictId(e.target.value)}
              className="bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 text-xs font-semibold rounded-md px-3 py-1.5 border border-zinc-200 dark:border-zinc-700 focus:outline-none focus:ring-2 focus:ring-accent-400/50"
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
          <MetricWithInfo
            label={t("socio.metrics.compositeStressScore")}
            value={selectedDistrict.composite_stress_index !== null ? selectedDistrict.composite_stress_index.toFixed(2) : t("common.noData")}
            info={t("socio.metrics.compositeStressScoreInfo")}
          />
          <MetricWithInfo
            label={t("socio.metrics.literacyRate")}
            value={selectedDistrict.literacy_rate !== null ? `${selectedDistrict.literacy_rate.toFixed(1)}%` : t("common.noData")}
            info={t("socio.metrics.literacyRateInfo")}
          />
          <MetricWithInfo
            label={t("socio.metrics.unemploymentRate")}
            value={selectedDistrict.unemployment_rate !== null ? `${selectedDistrict.unemployment_rate.toFixed(1)}%` : t("common.noData")}
            info={t("socio.metrics.unemploymentRateInfo")}
          />
          <MetricWithInfo
            label={t("socio.metrics.urbanizationLevel")}
            value={selectedDistrict.urbanization_pct !== null ? `${selectedDistrict.urbanization_pct.toFixed(1)}%` : t("common.noData")}
            info={t("socio.metrics.urbanizationLevelInfo")}
          />
        </div>
      )}

      {/* Analytics Tabs Navigation */}
      <div className="flex overflow-x-auto gap-1 border-b border-zinc-200 dark:border-zinc-800 pb-2">
        <button
          onClick={() => setActiveTab("overview")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "overview"
              ? "bg-accent-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          <span>{t("socio.tabs.overview")}</span>
        </button>

        <button
          onClick={() => setActiveTab("demographics")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "demographics"
              ? "bg-accent-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <UsersRound className="w-3.5 h-3.5" />
          <span>{t("socio.tabs.demographics")}</span>
        </button>

        <button
          onClick={() => setActiveTab("correlations")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "correlations"
              ? "bg-accent-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <BarChart3 className="w-3.5 h-3.5" />
          <span>{t("socio.tabs.correlations")}</span>
        </button>

        <button
          onClick={() => setActiveTab("gwr")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "gwr"
              ? "bg-accent-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <Map className="w-3.5 h-3.5" />
          <span>{t("socio.tabs.gwr")}</span>
        </button>

        <button
          onClick={() => setActiveTab("urbanization")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "urbanization"
              ? "bg-accent-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <Building2 className="w-3.5 h-3.5" />
          <span>{t("socio.tabs.urbanization")}</span>
        </button>

        <button
          onClick={() => setActiveTab("policy")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${
            activeTab === "policy"
              ? "bg-accent-600 text-white shadow-sm"
              : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"
          }`}
        >
          <Sparkles className="w-3.5 h-3.5" />
          <span>{t("socio.tabs.policy")}</span>
        </button>
      </div>

      {/* Tab Content Display */}
      <div className="space-y-6">
        {/* Tab 1: Socio-Economic Trends */}
        {activeTab === "overview" && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold text-zinc-900 dark:text-zinc-50">
                {t("socio.trends")}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {indicatorsQuery.isLoading ? (
                <LoadingSkeleton variant="card" rows={1} />
              ) : indicatorsQuery.isError ? (
                <ErrorState message={extractApiErrorMessage(indicatorsQuery.error)} onRetry={() => void indicatorsQuery.refetch()} />
              ) : !indicatorsQuery.data || indicatorsQuery.data.length === 0 ? (
                <EmptyState icon={UsersRound} title={t("socio.noIndicatorData")} />
              ) : (
                <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                  <TrendLineChart
                    data={indicatorsQuery.data}
                    xKey="year"
                    seriesKeys={[
                      { key: "literacy_rate", label: t("socio.metrics.literacyRate"), color: "#5f6299" },
                      { key: "unemployment_rate", label: t("socio.metrics.unemploymentRate"), color: "#b1503f" },
                      { key: "composite_stress_index", label: t("socio.metrics.compositeStressScore"), color: "#b8863f" },
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
              <EmptyState icon={UsersRound} title={t("socio.noVictimData")} description={victimDemographicsQuery.data.police_resource_recommendation} />
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
              <EmptyState icon={BarChart3} title={t("socio.insufficientData")} description={correlationsQuery.data.key_takeaway} />
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
                  {t("socio.spatialModel")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {gwrQuery.isLoading ? (
                  <LoadingSkeleton variant="card" rows={1} />
                ) : gwrQuery.isError ? (
                  <ErrorState message={extractApiErrorMessage(gwrQuery.error)} onRetry={() => void gwrQuery.refetch()} />
                ) : !gwrQuery.data || gwrQuery.data.length === 0 ? (
                  <EmptyState title={t("socio.noGwrData")} description={t("socio.noGwrDataDesc")} />
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
                  {t("socio.gwrMapHeatmap")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {gwrMapQuery.isLoading ? (
                  <LoadingSkeleton variant="card" rows={1} />
                ) : gwrMapQuery.isError ? (
                  <ErrorState message={extractApiErrorMessage(gwrMapQuery.error)} onRetry={() => void gwrMapQuery.refetch()} />
                ) : !gwrMapQuery.data || gwrMapQuery.data.length === 0 ? (
                  <EmptyState icon={Map} title={t("socio.noGwrMapData")} description={t("socio.noGwrMapDataDesc")} />
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
              <EmptyState icon={Building2} title={t("socio.notEnoughUrbanData")} description={t("socio.notEnoughUrbanDataDesc")} />
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
