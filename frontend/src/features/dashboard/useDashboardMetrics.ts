import { useQuery } from "@tanstack/react-query"

import { fetchCaseList } from "@/features/cases/casesApi"
import { extractApiErrorMessage } from "@/lib/api/httpClient"

const RECENT_CASE_WINDOW_SIZE = 8

export function useDashboardMetrics() {
  const query = useQuery({
    queryKey: ["dashboard-recent-cases"],
    queryFn: () => fetchCaseList({ limit: RECENT_CASE_WINDOW_SIZE }),
  })

  const recentCases = query.data ?? []
  const activeInvestigationCount = recentCases.length

  return {
    recentCases,
    activeInvestigationCount,
    isLoading: query.isLoading,
    isError: query.isError,
    errorMessage: query.error ? extractApiErrorMessage(query.error) : null,
    refetch: query.refetch,
  }
}
