import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Waypoints } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { useDebouncedValue } from "@/lib/hooks/useDebounce"
import { searchPersonsByName } from "@/features/persons/personsApi"
import { fetchEgoNetwork, fetchPredictedLinks } from "./networkApi"

const NetworkGraph = React.lazy(() => import("@/components/charts/NetworkGraph").then((m) => ({ default: m.NetworkGraph })))

function NetworkExplorerPage() {
  const [nameQuery, setNameQuery] = React.useState("")
  const [selectedPersonId, setSelectedPersonId] = React.useState<string | null>(null)
  const [depth, setDepth] = React.useState("2")
  const debouncedNameQuery = useDebouncedValue(nameQuery, 300)

  const { data: matches } = useQuery({
    queryKey: ["network-person-lookup", debouncedNameQuery],
    queryFn: () => searchPersonsByName(debouncedNameQuery),
    enabled: debouncedNameQuery.trim().length >= 2,
  })

  const egoQuery = useQuery({
    queryKey: ["ego-network", selectedPersonId, depth],
    queryFn: () => fetchEgoNetwork(selectedPersonId!, Number(depth)),
    enabled: Boolean(selectedPersonId),
  })

  const predictedLinksQuery = useQuery({
    queryKey: ["predicted-links", selectedPersonId],
    queryFn: () => fetchPredictedLinks(selectedPersonId!),
    enabled: Boolean(selectedPersonId),
  })

  const graphNodes = (egoQuery.data?.nodes ?? []).map((node) => ({
    id: node.id,
    label: typeof node.properties.name === "string" ? node.properties.name : node.id,
  }))
  const graphEdges = (egoQuery.data?.edges ?? []).map((edge) => ({
    id: edge.id,
    from: edge.from,
    to: edge.to,
    isPredicted: edge.type === "PREDICTED_LINK",
  }))

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Network Explorer</h1>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-72 space-y-1">
          <p className="section-label">Center person</p>
          <Input value={nameQuery} onChange={(event) => setNameQuery(event.target.value)} placeholder="Search by name..." />
          {matches && matches.length > 0 && nameQuery ? (
            <ul className="flat-surface max-h-40 overflow-y-auto rounded-md">
              {matches.map((person) => (
                <li key={person.id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedPersonId(person.id)
                      setNameQuery(person.full_name)
                    }}
                    className="block w-full px-2.5 py-1.5 text-left text-sm hover:bg-accent-50 dark:hover:bg-accent-900/40"
                  >
                    {person.full_name}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>

        <div className="w-32 space-y-1">
          <p className="section-label">Depth</p>
          <Select value={depth} onValueChange={setDepth}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["1", "2", "3", "4"].map((value) => (
                <SelectItem key={value} value={value}>
                  {value} hop{value === "1" ? "" : "s"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {!selectedPersonId ? (
        <Card>
          <CardContent>
            <EmptyState icon={Waypoints} title="Select a person to explore their network" />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Ego Network</CardTitle>
            </CardHeader>
            <CardContent>
              {egoQuery.isLoading ? (
                <LoadingSkeleton variant="card" rows={1} />
              ) : egoQuery.isError ? (
                <ErrorState message={extractApiErrorMessage(egoQuery.error)} onRetry={() => void egoQuery.refetch()} />
              ) : graphNodes.length === 0 ? (
                <EmptyState title="No network data" description="This person has no recorded connections yet." />
              ) : (
                <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                  <NetworkGraph nodes={graphNodes} edges={graphEdges} primaryNodeId={selectedPersonId} />
                </React.Suspense>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Predicted Links</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {predictedLinksQuery.isLoading ? (
                <LoadingSkeleton variant="list" rows={3} />
              ) : !predictedLinksQuery.data || predictedLinksQuery.data.length === 0 ? (
                <EmptyState title="No predicted links" description="No unconfirmed connections surfaced for this person." />
              ) : (
                <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
                  {predictedLinksQuery.data.map((link) => (
                    <li key={link.predicted_person_id} className="flex items-center justify-between px-4 py-2.5 text-sm">
                      <span className="text-zinc-700 dark:text-zinc-200">{link.name}</span>
                      <Badge variant="caution">{Math.round(link.confidence * 100)}% · {link.source_tool}</Badge>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}

export { NetworkExplorerPage }
