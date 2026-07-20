import * as React from "react"
import { useMutation } from "@tanstack/react-query"
import { MapPinned } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { fetchHotspotForecast } from "./trendsApi"

const HotspotMap = React.lazy(() => import("@/components/charts/HotspotMap").then((m) => ({ default: m.HotspotMap })))

const DEFAULT_CENTER_LAT = 12.9716
const DEFAULT_CENTER_LNG = 77.5946

function CrimeTrendsPage() {
  const [districtId, setDistrictId] = React.useState("1")
  const [crimeHeadId, setCrimeHeadId] = React.useState("1")
  const [targetDate, setTargetDate] = React.useState(() => new Date().toISOString().slice(0, 10))

  const forecastMutation = useMutation({
    mutationFn: () =>
      fetchHotspotForecast({
        districtId: Number(districtId),
        crimeHeadId: Number(crimeHeadId),
        targetDate,
      }),
  })

  const cells = forecastMutation.data ?? []
  const centerLat = cells[0]?.lat_center ?? DEFAULT_CENTER_LAT
  const centerLng = cells[0]?.lng_center ?? DEFAULT_CENTER_LNG

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Crime Trends &amp; Hotspot Forecast</h1>
      <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
        Hawkes/ETAS self-exciting forecast — decomposed into chronic background risk and acute near-repeat risk per
        grid cell.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Forecast Parameters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="trend-district">District ID</Label>
              <Input id="trend-district" value={districtId} onChange={(event) => setDistrictId(event.target.value)} className="w-28" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="trend-crime-head">Crime Head ID</Label>
              <Input id="trend-crime-head" value={crimeHeadId} onChange={(event) => setCrimeHeadId(event.target.value)} className="w-28" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="trend-date">Target Date</Label>
              <Input id="trend-date" type="date" value={targetDate} onChange={(event) => setTargetDate(event.target.value)} />
            </div>
            <Button onClick={() => forecastMutation.mutate()} disabled={forecastMutation.isPending}>
              {forecastMutation.isPending ? "Forecasting..." : "Run forecast"}
            </Button>
          </div>

          {forecastMutation.isError ? (
            <p className="text-xs text-critical-500">{extractApiErrorMessage(forecastMutation.error)}</p>
          ) : null}

          {forecastMutation.isPending ? (
            <LoadingSkeleton variant="card" rows={1} />
          ) : cells.length === 0 ? (
            <EmptyState icon={MapPinned} title="No forecast yet" description="Run a forecast to see the hotspot map for this district and crime type." />
          ) : (
            <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
              <HotspotMap cells={cells} centerLat={centerLat} centerLng={centerLng} />
            </React.Suspense>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export { CrimeTrendsPage }
