import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { UsersRound } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { fetchSocioIndicators } from "./socioApi"

const TrendLineChart = React.lazy(() => import("@/components/charts/TrendLineChart").then((m) => ({ default: m.TrendLineChart })))

function SocioInsightsPage() {
  const [districtId, setDistrictId] = React.useState("1")

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["socio-indicators", districtId],
    queryFn: () => fetchSocioIndicators(Number(districtId)),
    enabled: districtId.trim().length > 0,
  })

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Sociological Insights</h1>
      <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
        Place-level only — district-year aggregates, never joined to individual case or person records.
      </p>

      <Card>
        <CardHeader>
          <CardTitle>District Composite Indicators</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="socio-district">District ID</Label>
            <Input id="socio-district" value={districtId} onChange={(event) => setDistrictId(event.target.value)} className="w-32" />
          </div>

          {isLoading ? (
            <LoadingSkeleton variant="card" rows={1} />
          ) : isError ? (
            <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
          ) : !data || data.length === 0 ? (
            <EmptyState icon={UsersRound} title="No indicator data for this district" />
          ) : (
            <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
              <TrendLineChart
                data={data}
                xKey="year"
                seriesKeys={[
                  { key: "literacy_rate", label: "Literacy rate", color: "#5f6299" },
                  { key: "unemployment_rate", label: "Unemployment rate", color: "#b1503f" },
                  { key: "composite_stress_index", label: "Composite stress index", color: "#b8863f" },
                ]}
              />
            </React.Suspense>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export { SocioInsightsPage }
