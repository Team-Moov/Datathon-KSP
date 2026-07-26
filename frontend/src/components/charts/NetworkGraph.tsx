import * as React from "react"
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force"

import { cn } from "@/lib/utils"

// Data-driven color, not a Tailwind class list — community count is
// unbounded and JIT-purged utility classes can't be built from a dynamic
// index, so this cycles through real hex values via inline style instead
// (same approach GwrCentroidMap/HotspotMap already use for data-driven color).
const COMMUNITY_PALETTE = [
  "#5f6299", "#b1503f", "#b8863f", "#4c8c6b", "#8c5ba8",
  "#3f7fa6", "#a65f3f", "#6b8c4c", "#a83f7a", "#4c6b8c",
]

function colorForCommunity(communityId: number): string {
  return COMMUNITY_PALETTE[communityId % COMMUNITY_PALETTE.length]
}

interface RenderableNode extends SimulationNodeDatum {
  id: string
  label: string
  isPrimary?: boolean
  communityId?: number
}

interface RenderableEdge extends SimulationLinkDatum<RenderableNode> {
  id: string
  isPredicted: boolean
}

interface NetworkGraphProps {
  nodes: { id: string; label: string; communityId?: number }[]
  edges: { id: string; from: string; to: string; isPredicted: boolean }[]
  primaryNodeId?: string
  height?: number
  /** Fires on a click (not a drag) of a node — used to open a follow-up query. */
  onNodeSelect?: (node: { id: string; label: string }) => void
}

interface ViewTransform {
  x: number
  y: number
  k: number
}

const MIN_ZOOM = 0.3
const MAX_ZOOM = 4
// Pointer travel (screen px) below which a press-release counts as a click, not a drag.
const CLICK_SLOP = 4

/**
 * Force-directed layout over d3-force's physics engine (no off-the-shelf graph
 * package). SVG output so predicted-vs-confirmed edges and labels stay crisp at
 * any zoom. Interactive: scroll to zoom (toward the cursor), drag the background
 * to pan, drag a node to reposition it, click a node to drill in.
 */
function NetworkGraph({ nodes, edges, primaryNodeId, height = 420, actionLabel, onNodeSelect }: NetworkGraphProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const svgRef = React.useRef<SVGSVGElement>(null)
  const [viewportWidth, setViewportWidth] = React.useState(640)
  const [simulatedNodes, setSimulatedNodes] = React.useState<RenderableNode[]>([])
  const [simulatedEdges, setSimulatedEdges] = React.useState<RenderableEdge[]>([])
  const [transform, setTransform] = React.useState<ViewTransform>({ x: 0, y: 0, k: 1 })
  const [hoveredNodeId, setHoveredNodeId] = React.useState<string | null>(null)
  const [selectedNode, setSelectedNode] = React.useState<string | null>(null)

  // Spacing & label visibility controls
  const [showAllLabels, setShowAllLabels] = React.useState(false)
  const [spacious, setSpacious] = React.useState(false)

  // Entity node type filters for active decluttering — Accounts enabled by default so toggle is immediate
  const [showPersons, setShowPersons] = React.useState(true)
  const [showIncidents, setShowIncidents] = React.useState(true)
  const [showAccounts, setShowAccounts] = React.useState(true)

  // Relationship filters
  const [showConfirmedEdges, setShowConfirmedEdges] = React.useState(true)
  const [showPredictedEdges, setShowPredictedEdges] = React.useState(true)

  const simulationRef = React.useRef<any>(null)

  // Mutable pointer-gesture state kept in a ref so the pointer handlers don't
  // churn on every render (they're attached once, read the latest via the ref).
  const gestureRef = React.useRef<{
    mode: "none" | "pan" | "node"
    nodeId: string | null
    startClientX: number
    startClientY: number
    startTransform: ViewTransform
    moved: number
  }>({ mode: "none", nodeId: null, startClientX: 0, startClientY: 0, startTransform: transform, moved: 0 })

  React.useEffect(() => {
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width
      if (width) setViewportWidth(width)
    })
    if (containerRef.current) observer.observe(containerRef.current)
    return () => observer.disconnect()
  }, [])

  // Initialize and run the simulation dynamically on node/edge changes, spacious settings, and filters
  React.useEffect(() => {
    // 1. Filter nodes based on active checkboxes
    const filteredNodes = nodes.filter((node) => {
      const type = node.type || "Person"
      if (type === "Person" && !showPersons) return false
      if (type === "Incident" && !showIncidents) return false
      if (type === "Account" && !showAccounts) return false
      return true
    })

    const keptNodeIds = new Set(filteredNodes.map((n) => n.id))

    // 2. Filter edges based on visible nodes and relationship filters
    const filteredEdges = edges.filter((edge) => {
      if (!keptNodeIds.has(edge.from) || !keptNodeIds.has(edge.to)) return false
      if (edge.isPredicted && !showPredictedEdges) return false
      if (!edge.isPredicted && !showConfirmedEdges) return false
      return true
    })

    const nodeData: RenderableNode[] = filteredNodes.map((node) => ({
      id: node.id,
      label: node.label,
      isPrimary: node.id === primaryNodeId,
      communityId: node.communityId,
      type: node.type,
      properties: node.properties,
    }))
    
    const edgeData: RenderableEdge[] = filteredEdges.map((edge) => ({
      id: edge.id,
      source: edge.from,
      target: edge.to,
      isPredicted: edge.isPredicted,
    }))

    // Island cluster physics: strong link force pulls intra-cluster nodes together,
    // moderate repulsion pushes clusters apart, and weak positioning forces allow
    // disconnected components to float as separate islands across the canvas.
    const chargeStrength = spacious ? -350 : -220
    const chargeDistanceMax = spacious ? 550 : 400
    const linkDistance = spacious ? 55 : 35
    const collideRadius = spacious ? 22 : 14
    const linkForceStrength = 1.15

    const simulation = forceSimulation(nodeData)
      .force("charge", forceManyBody().strength(chargeStrength).distanceMax(chargeDistanceMax))
      .force("link", forceLink<RenderableNode, RenderableEdge>(edgeData).id((node) => node.id).distance(linkDistance).strength(linkForceStrength))
      .force("collide", forceCollide(collideRadius).strength(0.9))
      .force("x", forceX(viewportWidth / 2).strength(0.008))
      .force("y", forceY(height / 2).strength(0.008))
      .alphaDecay(0.025)

    simulationRef.current = simulation

    simulation.on("tick", () => {
      setSimulatedNodes([...nodeData])
      setSimulatedEdges([...edgeData])
    })

    setTransform({ x: 0, y: 0, k: 1 })
    setSelectedNode(null) // Reset details overlay on graph/filter changes

    return () => {
      simulation.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, primaryNodeId, spacious, showPersons, showIncidents, showAccounts, showConfirmedEdges, showPredictedEdges, viewportWidth, height])

  function resolveEndpoint(endpoint: RenderableEdge["source"] | RenderableEdge["target"]): RenderableNode | null {
    return typeof endpoint === "object" ? (endpoint as RenderableNode) : null
  }

  /** Screen (client) coordinates → graph coordinates, inverting the view transform. */
  function toGraphCoords(clientX: number, clientY: number): { x: number; y: number } {
    const rect = svgRef.current?.getBoundingClientRect()
    const sx = clientX - (rect?.left ?? 0)
    const sy = clientY - (rect?.top ?? 0)
    return { x: (sx - transform.x) / transform.k, y: (sy - transform.y) / transform.k }
  }

  function handleWheel(event: React.WheelEvent<SVGSVGElement>) {
    event.preventDefault()
    const rect = svgRef.current?.getBoundingClientRect()
    const px = event.clientX - (rect?.left ?? 0)
    const py = event.clientY - (rect?.top ?? 0)
    const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15
    setTransform((prev) => {
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, prev.k * factor))
      const scale = k / prev.k
      // Keep the point under the cursor fixed while zooming.
      return { k, x: px - (px - prev.x) * scale, y: py - (py - prev.y) * scale }
    })
  }

  function beginPan(event: React.PointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    gestureRef.current = {
      mode: "pan",
      nodeId: null,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startTransform: transform,
      moved: 0,
    }
    ;(event.currentTarget as SVGSVGElement).setPointerCapture(event.pointerId)
  }

  function beginNodeDrag(event: React.PointerEvent<SVGGElement>, nodeId: string) {
    event.stopPropagation()
    gestureRef.current = {
      mode: "node",
      nodeId,
      startClientX: event.clientX,
      startClientY: event.clientY,
      startTransform: transform,
      moved: 0,
    }
    ;(svgRef.current as SVGSVGElement).setPointerCapture(event.pointerId)
  }

  function handlePointerMove(event: React.PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current
    if (gesture.mode === "none") return
    const dx = event.clientX - gesture.startClientX
    const dy = event.clientY - gesture.startClientY
    gesture.moved = Math.max(gesture.moved, Math.hypot(dx, dy))

    if (gesture.mode === "pan") {
      setTransform({ ...gesture.startTransform, x: gesture.startTransform.x + dx, y: gesture.startTransform.y + dy })
    } else if (gesture.mode === "node" && gesture.nodeId) {
      const graph = toGraphCoords(event.clientX, event.clientY)
      setSimulatedNodes((prev) =>
        prev.map((node) => (node.id === gesture.nodeId ? { ...node, x: graph.x, y: graph.y } : node)),
      )
    }
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current
    // A near-stationary press-release on a node is a click → drill in.
    if (gesture.mode === "node" && gesture.nodeId && gesture.moved < CLICK_SLOP && onNodeSelect) {
      const node = simulatedNodes.find((candidate) => candidate.id === gesture.nodeId)
      if (node) onNodeSelect({ id: node.id, label: node.label })
    }
    gesture.mode = "none"
    gesture.nodeId = null
    try {
      ;(event.currentTarget as SVGSVGElement).releasePointerCapture(event.pointerId)
    } catch {
      /* pointer already released */
    }
  }

  const neighborIds = React.useMemo(() => {
    if (!hoveredNodeId) return null
    const ids = new Set<string>([hoveredNodeId])
    for (const edge of simulatedEdges) {
      const source = resolveEndpoint(edge.source)
      const target = resolveEndpoint(edge.target)
      if (source?.id === hoveredNodeId && target) ids.add(target.id)
      if (target?.id === hoveredNodeId && source) ids.add(source.id)
    }
    return ids
  }, [hoveredNodeId, simulatedEdges])

  function resetView() {
    setTransform({ x: 0, y: 0, k: 1 })
  }

  return (
    <div ref={containerRef} className="relative w-full overflow-hidden rounded-md">
      <svg
        ref={svgRef}
        width={viewportWidth}
        height={height}
        className="block touch-none select-none"
        style={{ cursor: gestureRef.current.mode === "pan" ? "grabbing" : "grab" }}
        onWheel={handleWheel}
        onPointerDown={beginPan}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerLeave={handlePointerUp}
      >
        <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.k})`}>
          <g>
            {simulatedEdges.map((edge) => {
              const source = resolveEndpoint(edge.source)
              const target = resolveEndpoint(edge.target)
              if (!source || !target || source.x == null || target.x == null) return null
              const dimmed = neighborIds != null && !(neighborIds.has(source.id) && neighborIds.has(target.id))
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
                    dimmed && "opacity-15",
                  )}
                />
              )
            })}
          </g>
          <g>
            {simulatedNodes.map((node) => {
              const dimmed = neighborIds != null && !neighborIds.has(node.id)
              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x ?? 0}, ${node.y ?? 0})`}
                  className={cn(onNodeSelect ? "cursor-pointer" : "cursor-grab", dimmed && "opacity-25")}
                  onPointerDown={(event) => beginNodeDrag(event, node.id)}
                  onPointerEnter={() => setHoveredNodeId(node.id)}
                  onPointerLeave={() => setHoveredNodeId((current) => (current === node.id ? null : current))}
                >
                  <circle
                    r={node.isPrimary ? 9 : 6}
                    style={node.communityId !== undefined && !node.isPrimary ? { fill: colorForCommunity(node.communityId) } : undefined}
                    className={
                      node.communityId !== undefined && !node.isPrimary
                        ? undefined
                        : node.isPrimary
                          ? "fill-accent-600 dark:fill-accent-400"
                          : "fill-zinc-400 dark:fill-zinc-600"
                    }
                  />
                  <text
                    x={0}
                    y={node.isPrimary ? 22 : 18}
                    textAnchor="middle"
                    className="pointer-events-none fill-zinc-600 text-[10px] dark:fill-zinc-400"
                  >
                    {node.label.length > 16 ? `${node.label.slice(0, 16)}...` : node.label}
                  </text>
                </g>
              )
            })}
          </g>
        </g>
      </svg>

      {transform.k !== 1 || transform.x !== 0 || transform.y !== 0 ? (
        <button
          type="button"
          onClick={resetView}
          className="absolute right-2 top-2 rounded border border-zinc-200 bg-white/90 px-1.5 py-0.5 text-[10px] text-zinc-500 shadow-sm hover:text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900/90 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          Reset view
        </button>
      ) : null}

      <div className="flex items-center gap-4 px-2 pb-2 pt-1 text-[11px] text-zinc-400">
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-4 bg-zinc-300 dark:bg-zinc-700" /> Confirmed
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-px w-4 border-t border-dashed border-caution-500/60" /> Predicted — unverified
        </span>
        <span className="ml-auto hidden sm:inline">Scroll to zoom · drag to pan{onNodeSelect ? " · click a node to explore" : ""}</span>
      </div>
    </div>
  )
}

export { NetworkGraph }
