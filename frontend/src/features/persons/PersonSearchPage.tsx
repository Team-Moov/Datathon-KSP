import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { UserSearch } from "lucide-react"
import { Link } from "react-router-dom"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { useDebouncedValue } from "@/lib/hooks/useDebounce"
import { searchPersonsByName } from "./personsApi"

function PersonSearchPage() {
  const [rawQuery, setRawQuery] = React.useState("")
  const debouncedQuery = useDebouncedValue(rawQuery, 300)
  const hasQuery = debouncedQuery.trim().length >= 2

  const { data: matches, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["person-search-page", debouncedQuery],
    queryFn: () => searchPersonsByName(debouncedQuery),
    enabled: hasQuery,
  })

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Person Search</h1>
      <Input
        value={rawQuery}
        onChange={(event) => setRawQuery(event.target.value)}
        placeholder="Search by name (min. 2 characters)..."
        className="max-w-md"
      />

      <Card>
        <CardHeader>
          <CardTitle>Results</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {!hasQuery ? (
            <EmptyState icon={UserSearch} title="Start typing to search" description="Cross-case identity records resolved by entity resolution." />
          ) : isLoading ? (
            <LoadingSkeleton variant="list" rows={4} />
          ) : isError ? (
            <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
          ) : !matches || matches.length === 0 ? (
            <EmptyState title="No matches" description={`Nothing found for "${debouncedQuery}"`} />
          ) : (
            <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
              {matches.map((person) => (
                <li key={person.id}>
                  <Link
                    to={`/persons/${person.id}`}
                    className="flex items-center justify-between px-4 py-2.5 text-sm transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900/60"
                  >
                    <span className="text-zinc-800 dark:text-zinc-100">{person.full_name}</span>
                    {!person.human_verified ? <Badge variant="neutral">unverified</Badge> : null}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export { PersonSearchPage }
