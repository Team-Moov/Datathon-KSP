import * as React from "react"

import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import type { WidgetEntry } from "./useChatSession"

const NetworkGraph = React.lazy(() => import("@/components/charts/NetworkGraph").then((m) => ({ default: m.NetworkGraph })))

interface RawGraphPayload {
  nodes?: { id: string; properties?: Record<string, unknown> }[]
  edges?: { id: string; from: string; to: string; type?: string }[]
}

function isGraphPayload(data: unknown): data is RawGraphPayload {
  return typeof data === "object" && data !== null && "nodes" in data
}

/** Fixed widget catalog per the design doc's generative-UI rule — the model
 * only ever picks a widget_type it already knows about; this component maps
 * each one to a real chart, it never renders arbitrary model-produced markup. */
function ChatWidgetRenderer({ widget }: { widget: WidgetEntry }) {
  if ((widget.widgetType === "force_directed_graph") && isGraphPayload(widget.data)) {
    const nodes = (widget.data.nodes ?? []).map((node) => ({
      id: node.id,
      label: typeof node.properties?.name === "string" ? (node.properties.name as string) : node.id,
    }))
    const edges = (widget.data.edges ?? []).map((edge) => ({
      id: edge.id,
      from: edge.from,
      to: edge.to,
      isPredicted: edge.type === "PREDICTED_LINK",
    }))
    return (
      <React.Suspense fallback={<LoadingSkeleton variant="card" rows={1} />}>
        <div className="flat-surface rounded-md p-2">
          <NetworkGraph nodes={nodes} edges={edges} height={280} />
        </div>
      </React.Suspense>
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
