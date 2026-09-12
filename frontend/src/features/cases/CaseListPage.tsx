import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { FileSearch } from "lucide-react"
import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { fetchCaseList } from "./casesApi"

function CaseListPage() {
  const { t } = useTranslation()
  const [crimeNoFilter, setCrimeNoFilter] = React.useState("")

  const { data: cases, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["case-list"],
    queryFn: () => fetchCaseList({ limit: 100 }),
  })

  const filteredCases = React.useMemo(() => {
    if (!cases) return []
    if (!crimeNoFilter.trim()) return cases
    const needle = crimeNoFilter.trim().toLowerCase()
    return cases.filter((caseSummary) => caseSummary.crime_no.toLowerCase().includes(needle))
  }, [cases, crimeNoFilter])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("cases.title")}</h1>
        <Input
          value={crimeNoFilter}
          onChange={(event) => setCrimeNoFilter(event.target.value)}
          placeholder={t("cases.filterPlaceholder")}
          className="w-64"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("cases.casesInScope")}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingSkeleton variant="table" rows={8} />
          ) : isError ? (
            <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
          ) : filteredCases.length === 0 ? (
            <EmptyState
              icon={FileSearch}
              title={t("cases.noCasesMatch")}
              description={t("cases.noCaptionDesc")}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("cases.colCrimeNo")}</TableHead>
                  <TableHead>{t("cases.dateReported")}</TableHead>
                  <TableHead>{t("common.district")}</TableHead>
                  <TableHead>{t("cases.colSource")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCases.map((caseSummary) => (
                  <TableRow key={caseSummary.id}>
                    <TableCell className="font-mono text-xs">
                      <Link to={`/cases/${caseSummary.id}`} className="text-accent-600 hover:underline dark:text-accent-300">
                        {caseSummary.crime_no}
                      </Link>
                    </TableCell>
                    <TableCell>{caseSummary.date_reported ?? "-"}</TableCell>
                    <TableCell>{caseSummary.district_id ?? "-"}</TableCell>
                    <TableCell className="uppercase text-xs text-zinc-500">{caseSummary.source_type}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export { CaseListPage }
