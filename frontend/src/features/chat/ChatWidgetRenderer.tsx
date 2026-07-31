import * as React from "react"
import { useTranslation } from "react-i18next"

import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import type { PredictedLink } from "@/components/charts/PredictedLinksList"
import type { MultiJurisdictionOffender } from "@/components/charts/MultiJurisdictionOffendersList"
import type { GwrRun } from "@/components/charts/GwrCoefficientsList"
import type { GwrDistrictPoint } from "@/components/charts/GwrCentroidMap"
import type { SuspiciousTransactionAlert } from "@/components/charts/FinancialAlertCard"
import type { RiskScoreResult } from "@/components/charts/RiskProfileCard"
import type { CaseBrief } from "@/components/charts/CaseBriefCard"
import type { CaseWorkspaceSummary } from "@/components/charts/CaseWorkspaceSummaryCard"
import type { ExtractedEntity } from "@/components/charts/EntitiesList"
import type { AlertListItem } from "@/components/charts/AlertsList"
import type { MoLinkageCluster } from "@/components/charts/MoLinkageList"
import type { PersonSearchResult } from "@/components/charts/PersonSearchResultsList"
import type { PersonAccount } from "@/features/financial/financialApi"
import type {
  DistrictOption,
  PolicyRecommendationsResponse,
  SocioCorrelationResponse,
  UrbanizationImpactItem,
  VictimDemographicsData,
} from "@/features/socio/socioApi"
import type { CrimeHeadOption } from "@/components/charts/CrimeHeadListCard"
import type { TemporalTrendsData } from "@/components/charts/TemporalTrendsChart"
import type { SurveillancePrioritiesData } from "@/components/charts/SurveillancePriorityList"
import type { WidgetEntry } from "./useChatSession"

const NetworkGraph = React.lazy(() => import("@/components/charts/NetworkGraph").then((m) => ({ default: m.NetworkGraph })))
const PredictedLinksList = React.lazy(() =>
  import("@/components/charts/PredictedLinksList").then((m) => ({ default: m.PredictedLinksList })),
)
const CentralityScoresList = React.lazy(() =>
  import("@/components/charts/CentralityScoresList").then((m) => ({ default: m.CentralityScoresList })),
)
const MultiJurisdictionOffendersList = React.lazy(() =>
  import("@/components/charts/MultiJurisdictionOffendersList").then((m) => ({ default: m.MultiJurisdictionOffendersList })),
)
const TrendLineChart = React.lazy(() => import("@/components/charts/TrendLineChart").then((m) => ({ default: m.TrendLineChart })))
const GwrCoefficientsList = React.lazy(() =>
  import("@/components/charts/GwrCoefficientsList").then((m) => ({ default: m.GwrCoefficientsList })),
)
const GwrCentroidMap = React.lazy(() => import("@/components/charts/GwrCentroidMap").then((m) => ({ default: m.GwrCentroidMap })))
const FinancialAlertCard = React.lazy(() =>
  import("@/components/charts/FinancialAlertCard").then((m) => ({ default: m.FinancialAlertCard })),
)
const HotspotMap = React.lazy(() => import("@/components/charts/HotspotMap").then((m) => ({ default: m.HotspotMap })))
const RiskProfileCard = React.lazy(() => import("@/components/charts/RiskProfileCard").then((m) => ({ default: m.RiskProfileCard })))
const CaseBriefCard = React.lazy(() => import("@/components/charts/CaseBriefCard").then((m) => ({ default: m.CaseBriefCard })))
const CaseWorkspaceSummaryCard = React.lazy(() =>
  import("@/components/charts/CaseWorkspaceSummaryCard").then((m) => ({ default: m.CaseWorkspaceSummaryCard })),
)
const EntitiesList = React.lazy(() => import("@/components/charts/EntitiesList").then((m) => ({ default: m.EntitiesList })))
const AlertsList = React.lazy(() => import("@/components/charts/AlertsList").then((m) => ({ default: m.AlertsList })))
const MoLinkageList = React.lazy(() => import("@/components/charts/MoLinkageList").then((m) => ({ default: m.MoLinkageList })))
const PersonSearchResultsList = React.lazy(() =>
  import("@/components/charts/PersonSearchResultsList").then((m) => ({ default: m.PersonSearchResultsList })),
)
const FinancialAccountsList = React.lazy(() =>
  import("@/components/charts/FinancialAccountsList").then((m) => ({ default: m.FinancialAccountsList })),
)
const DistrictListCard = React.lazy(() =>
  import("@/components/charts/DistrictListCard").then((m) => ({ default: m.DistrictListCard })),
)
const CrimeHeadListCard = React.lazy(() =>
  import("@/components/charts/CrimeHeadListCard").then((m) => ({ default: m.CrimeHeadListCard })),
)
const TemporalTrendsChart = React.lazy(() =>
  import("@/components/charts/TemporalTrendsChart").then((m) => ({ default: m.TemporalTrendsChart })),
)
const SurveillancePriorityList = React.lazy(() =>
  import("@/components/charts/SurveillancePriorityList").then((m) => ({ default: m.SurveillancePriorityList })),
)
const SocioCorrelationMatrix = React.lazy(() =>
  import("@/components/charts/SocioCorrelationMatrix").then((m) => ({ default: m.SocioCorrelationMatrix })),
)
const VictimDemographicsChart = React.lazy(() =>
  import("@/components/charts/VictimDemographicsChart").then((m) => ({ default: m.VictimDemographicsChart })),
)
const UrbanizationImpactChart = React.lazy(() =>
  import("@/components/charts/UrbanizationImpactChart").then((m) => ({ default: m.UrbanizationImpactChart })),
)
const PolicyRecommendationsCard = React.lazy(() =>
  import("@/components/charts/PolicyRecommendationsCard").then((m) => ({ default: m.PolicyRecommendationsCard })),
)

interface SocioIndicatorRow {
  year: number
}

interface CrimeStatRow {
  year: number
}

interface HotspotCell {
  lat_center: number
  lng_center: number
  predicted_rate: number
  background_component: number
  near_repeat_component: number
  forecast_date: string
}

function isFlowDiagramPayload(data: unknown): data is SuspiciousTransactionAlert | SuspiciousTransactionAlert[] {
  if (Array.isArray(data)) return true
  return typeof data === "object" && data !== null && "accounts_involved" in data
}

function isRiskProfilePayload(data: unknown): data is RiskScoreResult {
  return typeof data === "object" && data !== null && "shap_decomposition" in data
}

function isCaseBriefPayload(data: unknown): data is CaseBrief {
  return typeof data === "object" && data !== null && "context_summary" in data
}

function isCaseWorkspacePayload(data: unknown): data is CaseWorkspaceSummary {
  return typeof data === "object" && data !== null && "people" in data && "case" in data
}

function isSocioCorrelationPayload(data: unknown): data is SocioCorrelationResponse {
  return typeof data === "object" && data !== null && "correlations" in data
}

function isVictimDemographicsPayload(data: unknown): data is VictimDemographicsData {
  return typeof data === "object" && data !== null && "age_groups" in data
}

function isPolicyRecommendationsPayload(data: unknown): data is PolicyRecommendationsResponse {
  return typeof data === "object" && data !== null && "recommendations" in data
}

function isTemporalTrendsPayload(data: unknown): data is TemporalTrendsData {
  return typeof data === "object" && data !== null && "day_of_week" in data
}

function isSurveillancePrioritiesPayload(data: unknown): data is SurveillancePrioritiesData {
  return typeof data === "object" && data !== null && "checkpoints" in data
}

function isEntitiesPayload(data: unknown): data is { entities: ExtractedEntity[] } {
  return typeof data === "object" && data !== null && Array.isArray((data as { entities?: unknown }).entities)
}

interface RawGraphPayload {
  nodes?: { id: string; properties?: Record<string, unknown>; labels?: string[] }[]
  edges?: { id: string; from: string; to: string; type?: string }[]
}

function isGraphPayload(data: unknown): data is RawGraphPayload {
  return typeof data === "object" && data !== null && "nodes" in data
}

function isArrayPayload<T>(data: unknown): data is T[] {
  return Array.isArray(data)
}

function isCentralityPayload(data: unknown): data is Record<string, { pagerank?: number; betweenness?: number }> {
  return typeof data === "object" && data !== null && !Array.isArray(data)
}

function WidgetFrame({ label, children }: { label?: string; children: React.ReactNode }) {
  return (
    <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
      <div className="flat-surface rounded-md p-2">
        {label ? <p className="section-label mb-1.5 px-1">{label}</p> : null}
        {children}
      </div>
    </React.Suspense>
  )
}

/** Fixed widget catalog per the design doc's generative-UI rule — the model
 * only ever picks a widget_type it already knows about; this component maps
 * each one to a real chart, it never renders arbitrary model-produced markup.
 *
 * onFollowUpQuery closes the design doc's "two-way, not one-way" loop (§10.3):
 * clicking a node in a rendered graph fires a fresh question back into the same
 * conversation rather than leaving the visualization inert. */
function ChatWidgetRenderer({
  widget,
  onFollowUpQuery,
}: {
  widget: WidgetEntry
  onFollowUpQuery?: (query: string) => void
}) {
  const { t } = useTranslation()
  if (widget.widgetType === "force_directed_graph" && isGraphPayload(widget.data)) {
    const nodes = (widget.data.nodes ?? []).map((node) => ({
      id: node.id,
      label: typeof node.properties?.name === "string" ? (node.properties.name as string) : node.id,
      type: node.labels?.[0] || (node.id.startsWith("acc_") || node.id.includes("txn") || node.properties?.account_no ? "Account" : node.properties?.crime_no ? "Incident" : "Person"),
      properties: node.properties,
      communityId: typeof node.properties?.community_id === "number" ? (node.properties.community_id as number) : undefined,
    }))
    const edges = (widget.data.edges ?? []).map((edge) => ({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      isPredicted: edge.type === "PREDICTED_LINK",
    }))
    return (
      <WidgetFrame>
        <NetworkGraph
          nodes={nodes}
          edges={edges}
          height={280}
          actionLabel="Ask AI Assistant"
          onNodeSelect={
            onFollowUpQuery ? (node) => onFollowUpQuery(`Tell me more about ${node.label} — their network position, risk, and linked cases.`) : undefined
          }
        />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "person_search_results" && isArrayPayload<PersonSearchResult>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.matchedPersons")}>
        <PersonSearchResultsList results={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "financial_accounts_list" && isArrayPayload<PersonAccount>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.linkedFinancialAccounts")}>
        <FinancialAccountsList accounts={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "district_list" && isArrayPayload<DistrictOption>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.districts")}>
        <DistrictListCard districts={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "socio_correlation_matrix" && isSocioCorrelationPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.statisticalCorrelationMatrix")}>
        <SocioCorrelationMatrix data={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "victim_demographics" && isVictimDemographicsPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.victimDemographics")}>
        <VictimDemographicsChart data={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "urbanization_impact" && isArrayPayload<UrbanizationImpactItem>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.urbanizationVsCrimeVelocity")}>
        <UrbanizationImpactChart data={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "policy_recommendations" && isPolicyRecommendationsPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.policyRecommendations")}>
        <PolicyRecommendationsCard data={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "crime_head_list" && isArrayPayload<CrimeHeadOption>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.crimeCategories")}>
        <CrimeHeadListCard crimeHeads={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "temporal_trends" && isTemporalTrendsPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.temporalSeasonalTrends")}>
        <TemporalTrendsChart data={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "surveillance_priorities" && isSurveillancePrioritiesPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.surveillancePriorityCheckpoints")}>
        <SurveillancePriorityList data={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "predicted_links" && isArrayPayload<PredictedLink>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.predictedLinksUnverified")}>
        <PredictedLinksList links={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "centrality_scores" && isCentralityPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.centrality")}>
        <CentralityScoresList scores={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "multi_jurisdiction_offenders" && isArrayPayload<MultiJurisdictionOffender>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.multiJurisdictionOffenders")}>
        <MultiJurisdictionOffendersList offenders={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "socio_trend" && isArrayPayload<SocioIndicatorRow>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.socioEconomicIndicators")}>
        <TrendLineChart
          data={widget.data}
          xKey="year"
          seriesKeys={[
            { key: "literacy_rate", label: t("chatWidgets.literacyRate"), color: "#5f6299" },
            { key: "unemployment_rate", label: t("chatWidgets.unemploymentRate"), color: "#b1503f" },
            { key: "composite_stress_index", label: t("chatWidgets.compositeStressIndex"), color: "#b8863f" },
          ]}
          height={220}
        />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "gwr_coefficients" && isArrayPayload<GwrRun>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.gwrLocalPredictors")}>
        <GwrCoefficientsList runs={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "gwr_map" && isArrayPayload<GwrDistrictPoint>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.gwrStatewide")}>
        <GwrCentroidMap points={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "crime_stats_trend" && isArrayPayload<CrimeStatRow>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.crimeStatistics")}>
        <TrendLineChart
          data={widget.data}
          xKey="year"
          seriesKeys={[
            { key: "count", label: t("chatWidgets.count"), color: "#5f6299" },
            { key: "chi_weighted_count", label: t("chatWidgets.chiWeightedCount"), color: "#b1503f" },
          ]}
          height={220}
        />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "flow_diagram" && isFlowDiagramPayload(widget.data)) {
    const alerts = Array.isArray(widget.data) ? widget.data : [widget.data]
    if (alerts.length === 0) {
      return (
        <WidgetFrame label={t("chatWidgets.financialCrimeScan")}>
          <p className="px-1 text-xs text-zinc-400">{t("chatWidgets.noAlertTriggeredDesc")}</p>
        </WidgetFrame>
      )
    }
    return (
      <WidgetFrame label={t("chatWidgets.financialCrimeAlerts")}>
        <div className="space-y-2">
          {alerts.map((alert, index) => (
            <FinancialAlertCard key={index} alert={alert} />
          ))}
        </div>
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "hotspot_map" && isArrayPayload<HotspotCell>(widget.data)) {
    if (widget.data.length === 0) {
      return (
        <WidgetFrame label={t("chatWidgets.hotspotForecast")}>
          <p className="px-1 text-xs text-zinc-400">{t("chatWidgets.notEnoughHistoricalIncidents")}</p>
        </WidgetFrame>
      )
    }
    const centerLat = widget.data.reduce((sum, cell) => sum + cell.lat_center, 0) / widget.data.length
    const centerLng = widget.data.reduce((sum, cell) => sum + cell.lng_center, 0) / widget.data.length
    return (
      <WidgetFrame label={t("chatWidgets.hotspotForecast")}>
        <HotspotMap cells={widget.data} centerLat={centerLat} centerLng={centerLng} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "risk_profile_card" && isRiskProfilePayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.riskProfile")}>
        <RiskProfileCard result={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "case_timeline" && isCaseBriefPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.caseBrief")}>
        <CaseBriefCard brief={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "case_workspace" && isCaseWorkspacePayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.caseWorkspace")}>
        <CaseWorkspaceSummaryCard workspace={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "mo_linkage_clusters" && isArrayPayload<MoLinkageCluster>(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.moLinkage")}>
        <MoLinkageList clusters={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "alerts_list" && isArrayPayload<AlertListItem>(widget.data)) {
    return (
      <WidgetFrame label={t("nav.earlyWarningAlerts")}>
        <AlertsList alerts={widget.data} />
      </WidgetFrame>
    )
  }

  if (widget.widgetType === "entities_list" && isEntitiesPayload(widget.data)) {
    return (
      <WidgetFrame label={t("chatWidgets.extractedEntities")}>
        <EntitiesList entities={widget.data.entities} />
      </WidgetFrame>
    )
  }

  // ── Police staffing recommendation ────────────────────────────────────────
  if (
    widget.widgetType === "police_staffing_recommendation" &&
    typeof widget.data === "object" &&
    widget.data !== null &&
    "recommendation" in widget.data
  ) {
    const d = widget.data as {
      district_name: string
      calculated_at: string
      metrics: { unemployment_rate: string; urbanization_pct: string; composite_stress_index: string; recorded_incident_count: number }
      recommendation: {
        total_recommended_officers: number
        base_force_scale: number
        stress_multiplier: number
        allocations: Record<string, number>
        recommended_patrol_vehicles: number
        deployment_strategy: string
      }
    }
    const rec = d.recommendation
    return (
      <WidgetFrame label={`Staffing Estimate — ${d.district_name}`}>
        <div className="space-y-3 p-1">
          {/* KPI strip */}
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-md bg-indigo-50 dark:bg-indigo-950/30 p-2.5 text-center">
              <p className="text-lg font-bold text-indigo-700 dark:text-indigo-300">{rec.total_recommended_officers.toLocaleString()}</p>
              <p className="text-[10px] text-indigo-600/70 dark:text-indigo-400/70 mt-0.5">Recommended Officers</p>
            </div>
            <div className="rounded-md bg-emerald-50 dark:bg-emerald-950/30 p-2.5 text-center">
              <p className="text-lg font-bold text-emerald-700 dark:text-emerald-300">{rec.recommended_patrol_vehicles}</p>
              <p className="text-[10px] text-emerald-600/70 dark:text-emerald-400/70 mt-0.5">Patrol Vehicles</p>
            </div>
            <div className="rounded-md bg-amber-50 dark:bg-amber-950/30 p-2.5 text-center">
              <p className="text-lg font-bold text-amber-700 dark:text-amber-300">×{rec.stress_multiplier}</p>
              <p className="text-[10px] text-amber-600/70 dark:text-amber-400/70 mt-0.5">Stress Multiplier</p>
            </div>
          </div>
          {/* Driving metrics */}
          <div className="text-[10px] text-zinc-500 dark:text-zinc-400 flex flex-wrap gap-x-3 gap-y-1 px-1">
            <span>Unemployment: <strong className="text-zinc-700 dark:text-zinc-300">{d.metrics.unemployment_rate}</strong></span>
            <span>Urbanization: <strong className="text-zinc-700 dark:text-zinc-300">{d.metrics.urbanization_pct}</strong></span>
            <span>Stress Index: <strong className="text-zinc-700 dark:text-zinc-300">{d.metrics.composite_stress_index}</strong></span>
            <span>Incidents in DB: <strong className="text-zinc-700 dark:text-zinc-300">{d.metrics.recorded_incident_count}</strong></span>
          </div>
          {/* Allocation breakdown */}
          <div className="space-y-1.5 px-1">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Allocation Breakdown</p>
            {Object.entries(rec.allocations).map(([role, count]) => {
              const pct = Math.round((count / rec.total_recommended_officers) * 100)
              return (
                <div key={role} className="space-y-0.5">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-zinc-600 dark:text-zinc-300">{role}</span>
                    <span className="font-mono text-zinc-800 dark:text-zinc-200">{count.toLocaleString()} ({pct}%)</span>
                  </div>
                  <div className="h-1 rounded-full bg-zinc-200 dark:bg-zinc-800">
                    <div className="h-1 rounded-full bg-indigo-500" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              )
            })}
          </div>
          {/* Strategy note */}
          <p className="text-[10px] text-zinc-500 dark:text-zinc-400 leading-relaxed italic px-1">{rec.deployment_strategy}</p>
          <p className="text-[9px] text-zinc-400 dark:text-zinc-600 px-1">Calculated {d.calculated_at} · Model: stress-weighted base-force scale</p>
        </div>
      </WidgetFrame>
    )
  }

  return (
    <div className="flat-surface rounded-md p-3">
      <p className="section-label mb-1.5">{widget.widgetType.replace(/_/g, " ")}</p>
      <pre className="max-h-48 overflow-auto text-[11px] text-zinc-600 dark:text-zinc-300">
        {JSON.stringify(widget.data, null, 2)}
      </pre>
    </div>
  )
}

export { ChatWidgetRenderer }
