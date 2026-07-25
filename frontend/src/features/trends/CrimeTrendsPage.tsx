import * as React from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { useTranslation } from "react-i18next"
import { CalendarClock, Fingerprint, MapPinned, ShieldAlert } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import {
  fetchCrimeHeads,
  fetchHotspotForecast,
  fetchMoLinkageClusters,
  fetchSurveillancePriorities,
  fetchTemporalTrends,
  fetchTrendsDistricts,
} from "./trendsApi"

const HotspotMap = React.lazy(() => import("@/components/charts/HotspotMap").then((m) => ({ default: m.HotspotMap })))
const MoLinkageList = React.lazy(() => import("@/components/charts/MoLinkageList").then((m) => ({ default: m.MoLinkageList })))
const TemporalTrendsChart = React.lazy(() =>
  import("@/components/charts/TemporalTrendsChart").then((m) => ({ default: m.TemporalTrendsChart })),
)
const SurveillancePriorityList = React.lazy(() =>
  import("@/components/charts/SurveillancePriorityList").then((m) => ({ default: m.SurveillancePriorityList })),
)

const DEFAULT_CENTER_LAT = 12.9716
const DEFAULT_CENTER_LNG = 77.5946

type ActiveTab = "hotspots" | "temporal" | "mo" | "surveillance"

function CrimeTrendsPage() {
  const { t } = useTranslation()
  const [districtId, setDistrictId] = React.useState("")
  const [crimeHeadId, setCrimeHeadId] = React.useState("")
  const [targetDate, setTargetDate] = React.useState(() => new Date().toISOString().slice(0, 10))
  const [activeTab, setActiveTab] = React.useState<ActiveTab>("hotspots")

  const districtsQuery = useQuery({ queryKey: ["trends-districts"], queryFn: fetchTrendsDistricts })
  const crimeHeadsQuery = useQuery({ queryKey: ["trends-crime-heads"], queryFn: fetchCrimeHeads })

  // Auto-select the first district/crime head once reference data loads.
  React.useEffect(() => {
    if (districtsQuery.data && districtsQuery.data.length > 0 && !districtId) {
      setDistrictId(String(districtsQuery.data[0].district_id))
    }
  }, [districtsQuery.data, districtId])
  React.useEffect(() => {
    if (crimeHeadsQuery.data && crimeHeadsQuery.data.length > 0 && !crimeHeadId) {
      setCrimeHeadId(String(crimeHeadsQuery.data[0].id))
    }
  }, [crimeHeadsQuery.data, crimeHeadId])

  const districtIdNum = Number(districtId) || undefined
  const crimeHeadIdNum = Number(crimeHeadId) || undefined

  const forecastMutation = useMutation({
    mutationFn: () =>
      fetchHotspotForecast({ districtId: districtIdNum!, crimeHeadId: crimeHeadIdNum!, targetDate }),
  })

  const surveillanceMutation = useMutation({
    mutationFn: () =>
      fetchSurveillancePriorities({
        districtId: districtIdNum!,
        crimeHeadId: crimeHeadIdNum!,
        targetDate,
      }),
  })

  const temporalQuery = useQuery({
    queryKey: ["temporal-trends", districtIdNum, crimeHeadIdNum],
    queryFn: () => fetchTemporalTrends(districtIdNum!, crimeHeadIdNum),
    enabled: activeTab === "temporal" && districtIdNum !== undefined,
  })

  const moLinkageQuery = useQuery({
    queryKey: ["mo-linkage", crimeHeadIdNum],
    queryFn: () => fetchMoLinkageClusters(crimeHeadIdNum!),
    enabled: activeTab === "mo" && crimeHeadIdNum !== undefined,
  })

  const cells = forecastMutation.data ?? []
  const centerLat = cells[0]?.lat_center ?? DEFAULT_CENTER_LAT
  const centerLng = cells[0]?.lng_center ?? DEFAULT_CENTER_LNG
  const chronicVsAcute = React.useMemo(() => {
    if (cells.length === 0) return null
    const totalBg = cells.reduce((sum, c) => sum + c.background_component, 0)
    const totalNr = cells.reduce((sum, c) => sum + c.near_repeat_component, 0)
    const total = totalBg + totalNr
    if (total <= 0) return null
    return {
      chronicPct: Math.round((totalBg / total) * 1000) / 10,
      acutePct: Math.round((totalNr / total) * 1000) / 10,
    }
  }, [cells])

  const selectorsReady = districtIdNum !== undefined && crimeHeadIdNum !== undefined

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("trends.title")}</h1>
      <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
        {t("trends.description")}
      </p>

      <Card>
        <CardHeader>
          <CardTitle>{t("trends.scope")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="trend-district">{t("common.district")}</Label>
              <select
                id="trend-district"
                value={districtId}
                onChange={(event) => setDistrictId(event.target.value)}
                className="h-9 w-56 rounded-md border border-zinc-200 bg-white px-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
              >
                {(districtsQuery.data ?? []).map((d) => (
                  <option key={d.district_id} value={String(d.district_id)}>
                    {d.name} ({d.code})
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="trend-crime-head">{t("trends.crimeCategory")}</Label>
              <select
                id="trend-crime-head"
                value={crimeHeadId}
                onChange={(event) => setCrimeHeadId(event.target.value)}
                className="h-9 w-56 rounded-md border border-zinc-200 bg-white px-2 text-sm dark:border-zinc-800 dark:bg-zinc-900"
              >
                {(crimeHeadsQuery.data ?? []).map((c) => (
                  <option key={c.id} value={String(c.id)}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="trend-date">{t("trends.targetDate")}</Label>
              <Input id="trend-date" type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} />
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="flex overflow-x-auto gap-1 border-b border-zinc-200 dark:border-zinc-800 pb-2">
        <button
          onClick={() => setActiveTab("hotspots")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${activeTab === "hotspots" ? "bg-indigo-600 text-white shadow-sm" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
        >
          <MapPinned className="w-3.5 h-3.5" />
          <span>{t("trends.spatialHotspots")}</span>
        </button>
        <button
          onClick={() => setActiveTab("temporal")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${activeTab === "temporal" ? "bg-indigo-600 text-white shadow-sm" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
        >
          <CalendarClock className="w-3.5 h-3.5" />
          <span>{t("trends.temporalSeasonality")}</span>
        </button>
        <button
          onClick={() => setActiveTab("mo")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${activeTab === "mo" ? "bg-indigo-600 text-white shadow-sm" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
        >
          <Fingerprint className="w-3.5 h-3.5" />
          <span>{t("trends.moSerialClusters")}</span>
        </button>
        <button
          onClick={() => setActiveTab("surveillance")}
          className={`flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg transition-all ${activeTab === "surveillance" ? "bg-indigo-600 text-white shadow-sm" : "text-zinc-600 dark:text-zinc-400 hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
        >
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>{t("trends.surveillancePriority")}</span>
        </button>
      </div>

      {activeTab === "hotspots" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("trends.hawkesForecast")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Button onClick={() => forecastMutation.mutate()} disabled={forecastMutation.isPending || !selectorsReady}>
              {forecastMutation.isPending ? t("trends.forecasting") : t("trends.runForecast")}
            </Button>

            {forecastMutation.isError ? (
              <p className="text-xs text-critical-500">{extractApiErrorMessage(forecastMutation.error)}</p>
            ) : null}

            {forecastMutation.isPending ? (
              <LoadingSkeleton variant="card" rows={1} />
            ) : cells.length === 0 ? (
              <EmptyState icon={MapPinned} title={t("trends.noForecastYet")} description={t("trends.noForecastYetDesc")} />
            ) : (
              <>
                {chronicVsAcute ? (
                  <div className="flex items-center gap-4 rounded-md bg-zinc-50 dark:bg-zinc-800/50 px-3 py-2 text-xs">
                    <span className="section-label">{t("trends.chronicVsAcute")}</span>
                    <span className="font-medium text-indigo-600 dark:text-indigo-400">{t("trends.chronicBaseline")}: {chronicVsAcute.chronicPct}%</span>
                    <span className="font-medium text-amber-600 dark:text-amber-400">{t("trends.acuteNearRepeat")}: {chronicVsAcute.acutePct}%</span>
                  </div>
                ) : null}
                <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                  <HotspotMap cells={cells} centerLat={centerLat} centerLng={centerLng} />
                </React.Suspense>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "temporal" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("trends.dayOfWeek")}</CardTitle>
          </CardHeader>
          <CardContent>
            {temporalQuery.isLoading ? (
              <LoadingSkeleton variant="card" rows={2} />
            ) : temporalQuery.isError ? (
              <ErrorState message={extractApiErrorMessage(temporalQuery.error)} onRetry={() => void temporalQuery.refetch()} />
            ) : temporalQuery.data && temporalQuery.data.status === "insufficient_data" ? (
              <EmptyState icon={CalendarClock} title={t("trends.notEnoughCaseData")} description={t("trends.notEnoughCaseDataDesc")} />
            ) : temporalQuery.data ? (
              <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                <TemporalTrendsChart data={temporalQuery.data} />
              </React.Suspense>
            ) : null}
          </CardContent>
        </Card>
      )}

      {activeTab === "mo" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("trends.moBasedLinkage")}</CardTitle>
          </CardHeader>
          <CardContent>
            {moLinkageQuery.isLoading ? (
              <LoadingSkeleton variant="card" rows={2} />
            ) : moLinkageQuery.isError ? (
              <ErrorState message={extractApiErrorMessage(moLinkageQuery.error)} onRetry={() => void moLinkageQuery.refetch()} />
            ) : !moLinkageQuery.data || moLinkageQuery.data.length === 0 ? (
              <EmptyState icon={Fingerprint} title={t("trends.noMoSeries")} description={t("trends.noMoSeriesDesc")} />
            ) : (
              <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                <MoLinkageList clusters={moLinkageQuery.data} />
              </React.Suspense>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === "surveillance" && (
        <Card>
          <CardHeader>
            <CardTitle>{t("trends.surveillancePriorities")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              {t("trends.survRankingDesc")}
            </p>
            <Button onClick={() => surveillanceMutation.mutate()} disabled={surveillanceMutation.isPending || !selectorsReady}>
              {surveillanceMutation.isPending ? t("trends.ranking") : t("trends.rankPriorities")}
            </Button>
            {surveillanceMutation.isError ? (
              <p className="text-xs text-critical-500">{extractApiErrorMessage(surveillanceMutation.error)}</p>
            ) : null}
            {surveillanceMutation.isPending ? (
              <LoadingSkeleton variant="card" rows={1} />
            ) : !surveillanceMutation.data || surveillanceMutation.data.status === "insufficient_data" ? (
              <EmptyState icon={ShieldAlert} title={t("trends.noRankingYet")} description={t("trends.noRankingYetDesc")} />
            ) : (
              <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                <SurveillancePriorityList data={surveillanceMutation.data} />
              </React.Suspense>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}

export { CrimeTrendsPage }
