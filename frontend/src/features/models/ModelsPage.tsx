import { useQuery } from "@tanstack/react-query"
import { Cpu, ShieldCheck } from "lucide-react"

import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { fetchModelCards, type ModelCard } from "./modelsApi"

function ImportanceBars({ importance }: { importance: Record<string, number> }) {
  const entries = Object.entries(importance).sort((a, b) => b[1] - a[1])
  const max = Math.max(...entries.map(([, value]) => value), 0.0001)
  return (
    <div className="space-y-1.5">
      {entries.map(([feature, value]) => (
        <div key={feature}>
          <div className="mb-0.5 flex items-center justify-between text-xs">
            <span className="text-zinc-600 dark:text-zinc-300">{feature.replace(/_/g, " ")}</span>
            <span className="font-mono text-zinc-500">{value.toFixed(3)}</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-100 dark:bg-zinc-800">
            <div style={{ width: `${(value / max) * 100}%` }} className="h-full rounded-full bg-accent-500" />
          </div>
        </div>
      ))}
    </div>
  )
}

function ModelCardView({ card }: { card: ModelCard }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="size-4 text-zinc-400" />
              {card.name}
            </CardTitle>
            <p className="mt-0.5 text-xs text-zinc-500 dark:text-zinc-400">{card.task}</p>
          </div>
          <span className="rounded-full bg-accent-500/10 px-2 py-0.5 font-mono text-[10px] text-accent-700 dark:text-accent-300">
            {card.model_version}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
            {card.primary_metric.value.toFixed(3)}
          </span>
          <span className="text-xs text-zinc-500 dark:text-zinc-400">{card.primary_metric.label}</span>
        </div>

        <div className="text-xs text-zinc-500 dark:text-zinc-400">
          <span className="text-zinc-400">Family:</span> {card.family}
          <span className="mx-1.5">·</span>
          <span className="text-zinc-400">Serves:</span> {card.capability}
        </div>

        {card.feature_importance ? (
          <div>
            <p className="section-label mb-1.5">
              Feature importance{card.feature_importance_method ? ` (${card.feature_importance_method})` : ""}
            </p>
            <ImportanceBars importance={card.feature_importance} />
          </div>
        ) : null}

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-zinc-500 dark:text-zinc-400">
          {Object.entries(card.metrics).map(([key, value]) => (
            <span key={key}>
              <span className="text-zinc-400">{key.replace(/_/g, " ")}:</span>{" "}
              <span className="font-mono">{typeof value === "number" ? value.toFixed(3) : value}</span>
            </span>
          ))}
        </div>

        <div className="rounded-md border border-affirm-500/30 bg-affirm-500/5 p-2.5">
          <p className="mb-1 flex items-center gap-1.5 text-xs font-medium text-affirm-700 dark:text-affirm-400">
            <ShieldCheck className="size-3.5" />
            Fairness
            {card.fairness.protected_attributes_used === false ? (
              <span className="ml-1 font-normal text-zinc-500">
                — {card.fairness.protected_attributes.join(", ")} never modeled
              </span>
            ) : null}
          </p>
          <p className="text-[11px] leading-relaxed text-zinc-500 dark:text-zinc-400">{card.fairness.audit}</p>
        </div>
      </CardContent>
    </Card>
  )
}

function ModelsPage() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["model-cards"],
    queryFn: fetchModelCards,
  })

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Model Transparency</h1>
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Every ML model's held-out quality, feature importance, and fairness posture — the evidence behind each
          automated insight (capability #9).
        </p>
      </div>

      {isLoading ? (
        <LoadingSkeleton variant="card" rows={3} />
      ) : isError ? (
        <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data?.map((card) => <ModelCardView key={card.model_version} card={card} />)}
        </div>
      )}
    </div>
  )
}

export { ModelsPage }
