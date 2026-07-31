import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { Waypoints } from "lucide-react"
import { useSearchParams } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { PersonPicker, type PickedPerson } from "@/components/inputs/PersonPicker"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { fetchEgoNetwork, fetchPredictedLinks } from "./networkApi"

const NetworkGraph = React.lazy(() => import("@/components/charts/NetworkGraph").then((m) => ({ default: m.NetworkGraph })))

function NetworkExplorerPage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selected, setSelected] = React.useState<PickedPerson | null>(null)
  const [depth, setDepth] = React.useState("2")

  // Hydrate from a deep link (?person=<id>&name=<name>) once on mount.
  const hydratedRef = React.useRef(false)
  React.useEffect(() => {
    if (hydratedRef.current) return
    hydratedRef.current = true
    const personId = searchParams.get("person")
    if (personId) setSelected({ id: personId, name: searchParams.get("name") || t("network.selectedPerson") })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function selectPerson(person: PickedPerson) {
    setSelected(person)
    setSearchParams((prev) => {
      prev.set("person", person.id)
      prev.set("name", person.name)
      return prev
    })
  }

  function clearPerson() {
    setSelected(null)
    setSearchParams((prev) => {
      prev.delete("person")
      prev.delete("name")
      return prev
    })
  }

  const selectedPersonId = selected?.id ?? null

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
    label:
      typeof node.properties.account_no === "string"
        ? node.properties.account_no
        : typeof node.properties.name === "string"
          ? node.properties.name
          : node.id,
    type: node.labels?.[0] || "Person",
    properties: node.properties,
  }))
  const graphEdges = (egoQuery.data?.edges ?? []).map((edge) => ({
    id: edge.id,
    from: edge.from,
    to: edge.to,
    isPredicted: edge.type === "PREDICTED_LINK",
  }))

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("nav.networkExplorer")}</h1>

      <div className="flex flex-wrap items-end gap-3">
        <div className="w-72 space-y-1">
          <p className="section-label">{t("network.centerPerson")}</p>
          <PersonPicker selected={selected} onSelect={selectPerson} onClear={clearPerson} placeholder={t("network.searchByName")} />
        </div>

        <div className="w-32 space-y-1">
          <p className="section-label">{t("network.depth")}</p>
          <Select value={depth} onValueChange={setDepth}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["1", "2", "3", "4"].map((value) => (
                <SelectItem key={value} value={value}>
                  {value} {value === "1" ? t("network.hop") : t("network.hops")}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {!selectedPersonId ? (
        <Card>
          <CardContent>
            <EmptyState icon={Waypoints} title={t("network.selectPersonPrompt")} />
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>{t("network.egoNetwork")}</CardTitle>
            </CardHeader>
            <CardContent>
              {egoQuery.isLoading ? (
                <LoadingSkeleton variant="card" rows={1} />
              ) : egoQuery.isError ? (
                <ErrorState message={extractApiErrorMessage(egoQuery.error)} onRetry={() => void egoQuery.refetch()} />
              ) : graphNodes.length === 0 ? (
                <EmptyState title={t("network.noNetworkData")} description={t("network.noNetworkDataDesc")} />
              ) : (
                <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
                  <NetworkGraph
                    nodes={graphNodes}
                    edges={graphEdges}
                    primaryNodeId={selectedPersonId}
                    onNodeSelect={(node) => selectPerson({ id: node.id, name: node.label })}
                  />
                </React.Suspense>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("network.predictedLinks")}</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {predictedLinksQuery.isLoading ? (
                <LoadingSkeleton variant="list" rows={3} />
              ) : !predictedLinksQuery.data || predictedLinksQuery.data.length === 0 ? (
                <EmptyState title={t("network.noPredictedLinks")} description={t("network.noPredictedLinksDesc")} />
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
