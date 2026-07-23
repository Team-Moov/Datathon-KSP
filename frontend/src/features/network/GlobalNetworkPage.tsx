import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Loader2, Search, Waypoints } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { streamChatTurn } from "@/features/chat/chatApi"
import { fetchGraphSubset, type EgoNetworkResult } from "./networkApi"

const NetworkGraph = React.lazy(() => import("@/components/charts/NetworkGraph").then((m) => ({ default: m.NetworkGraph })))

const NODE_LABEL_OPTIONS = ["Person", "Incident", "Account"]
const EDGE_TYPE_OPTIONS = ["ACCUSED_IN", "VICTIM_IN", "WITNESSED", "ASSOCIATED_WITH", "TRANSACTED_WITH", "PREDICTED_LINK"]

function CheckboxGroup({
  label,
  options,
  selected,
  onToggle,
}: {
  label: string
  options: string[]
  selected: string[]
  onToggle: (value: string) => void
}) {
  return (
    <div className="space-y-1.5">
      <p className="section-label">{label}</p>
      <div className="flex flex-wrap gap-x-3 gap-y-1.5">
        {options.map((option) => (
          <label key={option} className="flex items-center gap-1.5 text-xs text-zinc-600 dark:text-zinc-300">
            <input
              type="checkbox"
              checked={selected.includes(option)}
              onChange={() => onToggle(option)}
              className="size-3.5 accent-accent-600"
            />
            {option.replace(/_/g, " ")}
          </label>
        ))}
      </div>
    </div>
  )
}

/**
 * Whole-network explorer — filter controls hit the deterministic /network/query
 * endpoint directly; the natural-language box instead streams through the same
 * /chat/ endpoint the assistant page uses (get_graph_subset is a registered
 * LLM tool), so free-text questions are resolved by the one central
 * orchestrator rather than a separate parsing path. Both render through the
 * same NetworkGraph, and clicking a node re-centers the filtered view on it.
 */
function GlobalNetworkPage() {
  const [nodeLabels, setNodeLabels] = React.useState<string[]>([])
  const [edgeTypes, setEdgeTypes] = React.useState<string[]>([])
  const [districtId, setDistrictId] = React.useState("")
  const [crimeNoContains, setCrimeNoContains] = React.useState("")
  const [dateFrom, setDateFrom] = React.useState("")
  const [dateTo, setDateTo] = React.useState("")
  const [centerPersonId, setCenterPersonId] = React.useState<string | undefined>(undefined)
  const [limit, setLimit] = React.useState("300")

  const [nlQuery, setNlQuery] = React.useState("")
  const [nlResult, setNlResult] = React.useState<EgoNetworkResult | null>(null)
  const [nlNarration, setNlNarration] = React.useState("")
  const [isNlRunning, setIsNlRunning] = React.useState(false)
  const [nlError, setNlError] = React.useState<string | null>(null)

  function toggleNodeLabel(value: string) {
    setNodeLabels((previous) => (previous.includes(value) ? previous.filter((entry) => entry !== value) : [...previous, value]))
  }
  function toggleEdgeType(value: string) {
    setEdgeTypes((previous) => (previous.includes(value) ? previous.filter((entry) => entry !== value) : [...previous, value]))
  }

  const filtersQuery = useQuery({
    queryKey: ["graph-subset", nodeLabels, edgeTypes, districtId, crimeNoContains, dateFrom, dateTo, centerPersonId, limit],
    queryFn: () =>
      fetchGraphSubset({
        nodeLabels: nodeLabels.length > 0 ? nodeLabels : undefined,
        edgeTypes: edgeTypes.length > 0 ? edgeTypes : undefined,
        districtId: districtId.trim() ? Number(districtId) : undefined,
        crimeNoContains: crimeNoContains.trim() || undefined,
        dateFrom: dateFrom || undefined,
        dateTo: dateTo || undefined,
        centerPersonId,
        limit: Number(limit) || 300,
      }),
  })

  const displayedResult = nlResult ?? filtersQuery.data
  const graphNodes = (displayedResult?.nodes ?? []).map((node) => ({
    id: node.id,
    label:
      typeof node.properties.name === "string"
        ? (node.properties.name as string)
        : typeof node.properties.crime_no === "string"
          ? (node.properties.crime_no as string)
          : node.id,
    communityId: typeof node.properties.community_id === "number" ? (node.properties.community_id as number) : undefined,
  }))
  const graphEdges = (displayedResult?.edges ?? []).map((edge) => ({
    id: edge.id,
    from: edge.from,
    to: edge.to,
    isPredicted: edge.type === "PREDICTED_LINK",
  }))

  async function runNaturalLanguageQuery() {
    const trimmed = nlQuery.trim()
    if (!trimmed || isNlRunning) return
    setIsNlRunning(true)
    setNlError(null)
    setNlNarration("")
    setNlResult(null)
    const abortController = new AbortController()
    try {
      for await (const event of streamChatTurn(crypto.randomUUID(), [{ role: "user", content: trimmed }], abortController.signal, "en")) {
        if (event.type === "widget" && event.widget_type === "force_directed_graph") {
          setNlResult(event.data as EgoNetworkResult)
        } else if (event.type === "token" && event.content) {
          setNlNarration((previous) => previous + event.content)
        } else if (event.type === "error") {
          setNlError(event.message ?? "Something went wrong.")
        }
      }
    } catch (error) {
      setNlError(error instanceof Error ? error.message : "Something went wrong.")
    } finally {
      setIsNlRunning(false)
    }
  }

  function clearNaturalLanguageResult() {
    setNlResult(null)
    setNlNarration("")
    setNlQuery("")
    setNlError(null)
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Global Network Graph</h1>
      <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
        Explore the whole network — persons, incidents, financial links — with filters, or ask in plain language
        (routed through the same assistant that powers the chat page).
      </p>

      <Card>
        <CardHeader>
          <CardTitle>Ask in plain language</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-end gap-3">
            <Input
              value={nlQuery}
              onChange={(event) => setNlQuery(event.target.value)}
              placeholder='e.g. "show accused persons in district 1 connected by transactions"'
              className="flex-1"
              onKeyDown={(event) => {
                if (event.key === "Enter") void runNaturalLanguageQuery()
              }}
            />
            <Button onClick={() => void runNaturalLanguageQuery()} disabled={!nlQuery.trim() || isNlRunning} className="gap-1.5">
              {isNlRunning ? <Loader2 className="size-4 animate-spin" /> : <Search className="size-4" />}
              Ask
            </Button>
            {nlResult ? (
              <Button variant="outline" onClick={clearNaturalLanguageResult}>
                Clear
              </Button>
            ) : null}
          </div>
          {nlError ? <p className="text-xs text-critical-500">{nlError}</p> : null}
          {nlNarration ? <p className="text-sm text-zinc-700 dark:text-zinc-300">{nlNarration}</p> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <CheckboxGroup label="Node types" options={NODE_LABEL_OPTIONS} selected={nodeLabels} onToggle={toggleNodeLabel} />
            <CheckboxGroup label="Edge types" options={EDGE_TYPE_OPTIONS} selected={edgeTypes} onToggle={toggleEdgeType} />
            <div className="space-y-1.5">
              <Label htmlFor="graph-district">District ID</Label>
              <Input id="graph-district" value={districtId} onChange={(event) => setDistrictId(event.target.value)} placeholder="Any" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="graph-crimeno">Crime No. contains</Label>
              <Input id="graph-crimeno" value={crimeNoContains} onChange={(event) => setCrimeNoContains(event.target.value)} placeholder="e.g. THEFT" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="graph-date-from">Reported from</Label>
              <Input id="graph-date-from" type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="graph-date-to">Reported to</Label>
              <Input id="graph-date-to" type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="graph-limit">Node limit</Label>
              <Input id="graph-limit" value={limit} onChange={(event) => setLimit(event.target.value)} />
            </div>
          </div>
          {centerPersonId ? (
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span>Centered on person {centerPersonId.slice(0, 8)}…</span>
              <Button variant="outline" size="sm" onClick={() => setCenterPersonId(undefined)}>
                Reset center
              </Button>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Graph{nlResult ? " — natural-language result" : ""}</CardTitle>
        </CardHeader>
        <CardContent>
          {nlResult ? (
            <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
              <NetworkGraph nodes={graphNodes} edges={graphEdges} height={520} onNodeSelect={(node) => setCenterPersonId(node.id)} />
            </React.Suspense>
          ) : filtersQuery.isLoading ? (
            <LoadingSkeleton variant="card" rows={1} />
          ) : filtersQuery.isError ? (
            <ErrorState message={extractApiErrorMessage(filtersQuery.error)} onRetry={() => void filtersQuery.refetch()} />
          ) : graphNodes.length === 0 ? (
            <EmptyState icon={Waypoints} title="No matching nodes" description="Adjust the filters above, or ask a question in plain language." />
          ) : (
            <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
              <NetworkGraph nodes={graphNodes} edges={graphEdges} height={520} onNodeSelect={(node) => setCenterPersonId(node.id)} />
            </React.Suspense>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export { GlobalNetworkPage }
