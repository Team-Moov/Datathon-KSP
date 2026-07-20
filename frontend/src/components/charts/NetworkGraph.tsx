import * as React from "react"
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force"

import { cn } from "@/lib/utils"

interface RenderableNode extends SimulationNodeDatum {
  id: string
  label: string
  isPrimary?: boolean
}

interface RenderableEdge extends SimulationLinkDatum<RenderableNode> {
  id: string
  isPredicted: boolean
}

interface NetworkGraphProps {
  nodes: { id: string; label: string }[]
  edges: { id: string; from: string; to: string; isPredicted: boolean }[]
  primaryNodeId?: string
  height?: number
  onNodeSelect?: (nodeId: string) => void
}

/**
 * Hand-rolled force-directed layout over d3-force's physics engine (no
 * off-the-shelf graph-rendering package) — SVG output so predicted-vs-confirmed
 * edges and node labels stay crisp at any zoom level.
 */
function NetworkGraph({ nodes, edges, primaryNodeId, height = 420, onNodeSelect }: NetworkGraphProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const [viewportWidth, setViewportWidth] = React.useState(640)
  const [simulatedNodes, setSimulatedNodes] = React.useState<RenderableNode[]>([])
  const [simulatedEdges, setSimulatedEdges] = React.useState<RenderableEdge[]>([])

  React.useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width
      if (width) setViewportWidth(width)
    })
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  React.useEffect(() => {
    const nodeData: RenderableNode[] = nodes.map((node) => ({
      id: node.id,
      label: node.label,
      isPrimary: node.id === primaryNodeId,
    }))
    const edgeData: RenderableEdge[] = edges.map((edge) => ({
      id: edge.id,
      source: edge.from,
      target: edge.to,
      isPredicted: edge.isPredicted,
    }))

    const simulation = forceSimulation(nodeData)
      .force("charge", forceManyBody().strength(-220))
      .force("link", forceLink<RenderableNode, RenderableEdge>(edgeData).id((node) => node.id).distance(90))
      .force("center", forceCenter(viewportWidth / 2, height / 2))
      .force("collide", forceCollide(26))
      .stop()

    simulation.tick(240)
    setSimulatedNodes([...nodeData])
    setSimulatedEdges([...edgeData])

    return () => {
      simulation.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, primaryNodeId, viewportWidth, height])

  function resolveEndpoint(endpoint: RenderableEdge["source"] | RenderableEdge["target"]): RenderableNode | null {
    return typeof endpoint === "object" ? (endpoint as RenderableNode) : null
  }

  return (
    <div ref={containerRef} className="w-full overflow-hidden rounded-md">
      <svg width={viewportWidth} height={height} className="block">
        <g>
          {simulatedEdges.map((edge) => {
            const source = resolveEndpoint(edge.source)
            const target = resolveEndpoint(edge.target)
            if (!source || !target || source.x == null || target.x == null) return null
            return (
              <line
                key={edge.id}
                x1={source.x}
                y1={source.y}
                x2={target.x}
                y2={target.y}
                strokeWidth={edge.isPredicted ? 1 : 1.5}
                strokeDasharray={edge.isPredicted ? "4 3" : undefined}
                className={cn(
                  edge.isPredicted ? "stroke-caution-500/50" : "stroke-zinc-300 dark:stroke-zinc-700",
                )}
              />
            )
          })}
        </g>
        <g>
          {simulatedNodes.map((node) => (
            <g
              key={node.id}
              transform={`translate(${node.x ?? 0}, ${node.y ?? 0})`}
              className={onNodeSelect ? "cursor-pointer" : undefined}
              onClick={() => onNodeSelect?.(node.id)}
            >
              <circle
                r={node.isPrimary ? 9 : 6}
                className={
                  node.isPrimary
                    ? "fill-accent-600 dark:fill-accent-400"
                    : "fill-zinc-400 dark:fill-zinc-600"
                }
              />
              <text
                x={0}
                y={node.isPrimary ? 22 : 18}
                textAnchor="middle"
                className="fill-zinc-600 text-[10px] dark:fill-zinc-400"
              >
                {node.label.length > 16 ? `${node.label.slice(0, 16)}...` : node.label}
              </text>
            </g>
          ))}
        </g>
      </svg>
      <div className="flex items-center gap-4 px-2 pb-2 text-[11px] text-zinc-400">
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-4 bg-zinc-300 dark:bg-zinc-700" /> Confirmed
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-4 border-t border-dashed border-caution-500/60" /> Predicted — unverified
        </span>
      </div>
    </div>
  )
}

export { NetworkGraph }
