import { ShapDecompositionBars } from "@/components/charts/ShapDecompositionBars"

interface ModelCard {
  primary_metric?: { label: string; value: number }
  feature_importance?: Record<string, number> | null
  fairness?: { protected_attributes_used?: boolean }
}

interface RiskScoreResult {
  score_id: string
  person_id: string
  score: number
  model_version: string
  shap_decomposition: Record<string, number>
  model_card?: ModelCard | null
  human_reviewed: boolean
  computed_at: string
  disclaimer: string
}

function dominantFeature(importance: Record<string, number>): string | null {
  const entries = Object.entries(importance)
  if (entries.length === 0) return null
  const [key] = entries.reduce((best, current) => (current[1] > best[1] ? current : best))
  return key.replace(/_/g, " ")
}

/** Never a bare number — the score always ships with its SHAP-style decomposition,
 * the model's held-out quality metric, and the human-review/disclaimer context
 * alongside it (§7.4, capability #9). */
function RiskProfileCard({ result }: { result: RiskScoreResult }) {
  const card = result.model_card ?? null
  const dominant = card?.feature_importance ? dominantFeature(card.feature_importance) : null
  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">{result.score.toFixed(2)}</span>
        <span className="text-[10px] text-zinc-400">
          {result.model_version} · {result.human_reviewed ? "human-reviewed" : "pending review"}
        </span>
      </div>
      <ShapDecompositionBars decomposition={result.shap_decomposition} />
      {card?.primary_metric || dominant ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 border-t border-zinc-100 pt-2 text-[10px] text-zinc-400 dark:border-zinc-800">
          {card?.primary_metric ? (
            <span>
              Model {card.primary_metric.label}: <span className="font-mono">{card.primary_metric.value.toFixed(3)}</span>
            </span>
          ) : null}
          {dominant ? <span>Dominant feature: {dominant}</span> : null}
          {card?.fairness?.protected_attributes_used === false ? <span>No protected attributes used</span> : null}
        </div>
      ) : null}
      <p className="text-[11px] italic text-zinc-400 dark:text-zinc-600">{result.disclaimer}</p>
    </div>
  )
}

export { RiskProfileCard }
export type { RiskScoreResult }
