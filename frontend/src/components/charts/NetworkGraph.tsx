import * as React from "react"
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force"
import { X } from "lucide-react"

import { cn } from "@/lib/utils"

// Data-driven color palette for community clusters
const COMMUNITY_PALETTE = [
  "#5f6299", "#b1503f", "#b8863f", "#4c8c6b", "#8c5ba8",
  "#3f7fa6", "#a65f3f", "#6b8c4c", "#a83f7a", "#4c6b8c",
]

function colorForCommunity(communityId: number): string {
  return COMMUNITY_PALETTE[communityId % COMMUNITY_PALETTE.length]
}

const TYPE_COLORS: Record<string, string> = {
  Person: "#6366f1",    // Indigo
  Incident: "#f43f5e",  // Rose
  Account: "#10b981",   // Emerald
}

interface RenderableNode extends SimulationNodeDatum {
  id: string
  label: string
  isPrimary?: boolean
  communityId?: number
  type?: string
  properties?: Record<string, any>
}

interface RenderableEdge extends SimulationLinkDatum<RenderableNode> {
  id: string
  isPredicted: boolean
}

interface NetworkGraphProps {
  nodes: { id: string; label: string; type?: string; properties?: Record<string, any>; communityId?: number }[]
  edges: { id: string; from: string; to: string; isPredicted: boolean }[]
  primaryNodeId?: string
  height?: number
  actionLabel?: string
  /** Fires when user clicks node's primary action in the detail card or drills in */
  onNodeSelect?: (node: { id: string; label: string }) => void
}

interface ViewTransform {
  x: number
  y: number
  k: number
}

const MIN_ZOOM = 0.3
const MAX_ZOOM = 4
const CLICK_SLOP = 4

/**
 * Hand-rolled force-directed layout over d3-force's physics engine.
 * Interactive graph with hover highlighting, entity toggles, spacing controls,
 * and a sleek floating detail card on node selection.
 */
function NetworkGraph({ nodes, edges, primaryNodeId, height = 520, actionLabel, onNodeSelect }: NetworkGraphProps) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const svgRef = React.useRef<SVGSVGElement>(null)
  const [viewportWidth, setViewportWidth] = React.useState(640)
  const [simulatedNodes, setSimulatedNodes] = React.useState<RenderableNode[]>([])
  const [simulatedEdges, setSimulatedEdges] = React.useState<RenderableEdge[]>([])
  const [transform, setTransform] = React.useState<ViewTransform>({ x: 0, y: 0, k: 1 })
  const [hoveredNodeId, setHoveredNodeId] = React.useState<string | null>(null)
  const [selectedNode, setSelectedNode] = React.useState<RenderableNode | null>(null)

  // Spacing & label visibility controls
  const [showAllLabels, setShowAllLabels] = React.useState(false)
  const [spacious, setSpacious] = React.useState(false)

  // Entity type filters
  const [showPersons, setShowPersons] = React.useState(true)
  const [showIncidents, setShowIncidents] = React.useState(true)
  const [showAccounts, setShowAccounts] = React.useState(true)

  // Relationship filters
  const [showConfirmedEdges, setShowConfirmedEdges] = React.useState(true)
  const [showPredictedEdges, setShowPredictedEdges] = React.useState(true)

  const simulationRef = React.useRef<any>(null)

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

  // Initialize and run the simulation dynamically on node/edge changes and filters
  React.useEffect(() => {
    const filteredNodes = nodes.filter((node) => {
      const type = node.type || "Person"
      if (type === "Person" && !showPersons) return false
      if (type === "Incident" && !showIncidents) return false
      if (type === "Account" && !showAccounts) return false
      return true
    })

    const keptNodeIds = new Set(filteredNodes.map((n) => n.id))

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

    // Keep the graph compact enough to remain readable at the default zoom.
    // The positional forces prevent disconnected components from drifting out
    // of the viewport while the link/collision forces preserve local structure.
    const chargeStrength = spacious ? -350 : -220
    const linkDistance = spacious ? 100 : 64
    const collideRadius = spacious ? 28 : 20

    const simulation = forceSimulation(nodeData)
      .stop()
      .force("charge", forceManyBody().strength(chargeStrength).distanceMax(spacious ? 520 : 360))
      .force("link", forceLink<RenderableNode, RenderableEdge>(edgeData).id((node) => node.id).distance(linkDistance))
      .force("center", forceCenter(viewportWidth / 2, height / 2))
      .force("x", forceX(viewportWidth / 2).strength(0.035))
      .force("y", forceY(height / 2).strength(0.035))
      .force("collide", forceCollide(collideRadius).strength(0.9))

    // Run the deterministic layout before rendering it. Keeping a live d3
    // timer here triggered a React state update for every physics tick, which
    // made dense graphs flicker and made node positions feel unstable.
    simulation.tick(260)
    simulation.stop()

    simulationRef.current = simulation
    setSimulatedNodes([...nodeData])
    setSimulatedEdges([...edgeData])

    setTransform({ x: 0, y: 0, k: 1 })
    setSelectedNode(null)

    return () => {
      simulation.stop()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, primaryNodeId, spacious, showPersons, showIncidents, showAccounts, showConfirmedEdges, showPredictedEdges, viewportWidth, height])

  function resolveEndpoint(endpoint: RenderableEdge["source"] | RenderableEdge["target"]): RenderableNode | null {
    return typeof endpoint === "object" ? (endpoint as RenderableNode) : null
  }

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
      return { k, x: px - (px - prev.x) * scale, y: py - (py - prev.y) * scale }
    })
  }

  function beginPan(event: React.PointerEvent<SVGSVGElement>) {
    if (event.button !== 0) return
    const gesture = gestureRef.current
    gesture.mode = "pan"
    gesture.nodeId = null
    gesture.startClientX = event.clientX
    gesture.startClientY = event.clientY
    gesture.startTransform = { ...transform }
    gesture.moved = 0
    try {
      ;(event.currentTarget as SVGSVGElement).setPointerCapture(event.pointerId)
    } catch {
      /* ignore */
    }
  }

  function beginNodeDrag(event: React.PointerEvent<SVGGElement>, nodeId: string) {
    event.stopPropagation()
    if (event.button !== 0) return
    const gesture = gestureRef.current
    gesture.mode = "node"
    gesture.nodeId = nodeId
    gesture.startClientX = event.clientX
    gesture.startClientY = event.clientY
    gesture.startTransform = { ...transform }
    gesture.moved = 0
    try {
      if (svgRef.current) svgRef.current.setPointerCapture(event.pointerId)
    } catch {
      /* ignore */
    }
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
      const coords = toGraphCoords(event.clientX, event.clientY)
      setSimulatedNodes((prev) =>
        prev.map((node) => (node.id === gesture.nodeId ? { ...node, x: coords.x, y: coords.y } : node)),
      )
    }
  }

  function handlePointerUp(event: React.PointerEvent<SVGSVGElement>) {
    const gesture = gestureRef.current
    if (gesture.mode === "node" && gesture.nodeId && gesture.moved < CLICK_SLOP) {
      const clicked = simulatedNodes.find((candidate) => candidate.id === gesture.nodeId)
      if (clicked) setSelectedNode(clicked)
    }
    gesture.mode = "none"
    gesture.nodeId = null
    try {
      ;(event.currentTarget as SVGSVGElement).releasePointerCapture(event.pointerId)
    } catch {
      /* ignore */
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
    <div ref={containerRef} className="relative w-full overflow-hidden rounded-md border border-zinc-200 dark:border-zinc-800 bg-zinc-950/30">
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
          {/* Edges */}
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
                    edge.isPredicted ? "stroke-caution-500/50" : "stroke-zinc-400 dark:stroke-zinc-700",
                    dimmed && "opacity-15",
                  )}
                />
              )
            })}
          </g>

          {/* Nodes */}
          <g>
            {simulatedNodes.map((node) => {
              const dimmed = neighborIds != null && !neighborIds.has(node.id)
              const typeColor = node.type ? TYPE_COLORS[node.type] : undefined
              const isHovered = hoveredNodeId === node.id
              const isSelected = selectedNode?.id === node.id

              const showLabel = showAllLabels ||
                                node.isPrimary ||
                                isHovered ||
                                isSelected ||
                                (neighborIds != null && neighborIds.has(node.id))

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x ?? 0}, ${node.y ?? 0})`}
                  className={cn("cursor-pointer", dimmed && "opacity-25")}
                  onPointerDown={(event) => beginNodeDrag(event, node.id)}
                  onPointerEnter={() => setHoveredNodeId(node.id)}
                  onPointerLeave={() => setHoveredNodeId((current) => (current === node.id ? null : current))}
                >
                  {(isHovered || isSelected) && (
                    <circle
                      r={node.isPrimary ? 14 : 11}
                      className={cn(
                        "fill-none stroke-2 animate-pulse",
                        node.isPrimary
                          ? "stroke-accent-400 dark:stroke-accent-400"
                          : node.type === "Person"
                          ? "stroke-indigo-400 dark:stroke-indigo-400"
                          : node.type === "Incident"
                          ? "stroke-rose-400 dark:stroke-rose-400"
                          : node.type === "Account"
                          ? "stroke-emerald-400 dark:stroke-emerald-400"
                          : "stroke-zinc-400"
                      )}
                    />
                  )}

                  <circle
                    r={node.isPrimary ? 9 : 6}
                    style={
                      node.isPrimary
                        ? undefined
                        : typeColor
                          ? { fill: typeColor }
                          : node.communityId !== undefined
                            ? { fill: colorForCommunity(node.communityId) }
                            : undefined
                    }
                    className={
                      node.isPrimary
                        ? "fill-accent-600 dark:fill-accent-400 stroke-zinc-100 dark:stroke-zinc-900 stroke-2"
                        : typeColor
                          ? "stroke-zinc-100 dark:stroke-zinc-900 stroke-1"
                          : node.communityId !== undefined
                            ? "stroke-zinc-100 dark:stroke-zinc-900 stroke-1"
                            : "fill-zinc-400 dark:fill-zinc-600 stroke-zinc-100 dark:stroke-zinc-900 stroke-1"
                    }
                  />

                  {showLabel && (
                    <text
                      x={0}
                      y={node.isPrimary ? 22 : 18}
                      textAnchor="middle"
                      className="pointer-events-none fill-zinc-300 font-medium text-[10px] drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]"
                    >
                      {node.label.length > 16 ? `${node.label.slice(0, 16)}...` : node.label}
                    </text>
                  )}
                </g>
              )
            })}
          </g>
        </g>
      </svg>

      {/* Floating Node Details Card Overlay (on Node Click) */}
      {selectedNode && (
        <div className="absolute left-3 bottom-12 z-20 w-64 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white/95 dark:bg-zinc-900/95 p-3 shadow-lg backdrop-blur-md text-xs space-y-2 animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-start justify-between gap-2 border-b border-zinc-150 dark:border-zinc-800 pb-1.5">
            <div>
              <span
                className={cn(
                  "inline-block rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider mb-1",
                  selectedNode.type === "Person"
                    ? "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300"
                    : selectedNode.type === "Incident"
                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300"
                    : selectedNode.type === "Account"
                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300"
                    : "bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-300"
                )}
              >
                {selectedNode.type || "Entity"} Details
              </span>
              <h4 className="font-bold text-zinc-900 dark:text-zinc-100 text-xs leading-tight">
                {selectedNode.label}
              </h4>
            </div>
            <button
              type="button"
              onClick={() => setSelectedNode(null)}
              className="rounded p-0.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
            >
              <X className="size-3.5" />
            </button>
          </div>

          {/* Properties List */}
          {selectedNode.properties && Object.keys(selectedNode.properties).length > 0 && (
            <div className="space-y-1 max-h-28 overflow-y-auto text-[10px] text-zinc-600 dark:text-zinc-400 font-mono">
              {Object.entries(selectedNode.properties).map(([key, val]) => (
                <div key={key} className="flex justify-between gap-2">
                  <span className="text-zinc-450 dark:text-zinc-500 uppercase text-[8.5px]">{key.replace(/_/g, " ")}:</span>
                  <span className="truncate text-zinc-800 dark:text-zinc-200 font-semibold">{String(val)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Quick-Action Matrix */}
          <div className="pt-1.5 space-y-1.5 border-t border-zinc-150 dark:border-zinc-800">
            <p className="text-[9px] font-bold uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Quick Actions</p>

            {selectedNode.type === "Person" && (
              <div className="grid grid-cols-2 gap-1.5">
                <a
                  href={`/persons?query=${encodeURIComponent(selectedNode.label)}`}
                  className="flex items-center justify-center rounded bg-indigo-50 border border-indigo-100 hover:bg-indigo-100 dark:bg-indigo-950/40 dark:border-indigo-900 dark:hover:bg-indigo-900/60 px-2 py-1 text-[10px] font-semibold text-indigo-700 dark:text-indigo-300 transition text-center"
                >
                  View Profile
                </a>
                {onNodeSelect ? (
                  <button
                    type="button"
                    onClick={() => {
                      onNodeSelect({ id: selectedNode.id, label: selectedNode.label })
                      setSelectedNode(null)
                    }}
                    className="rounded bg-accent-600 hover:bg-accent-700 text-white px-2 py-1 text-[10px] font-semibold transition text-center cursor-pointer"
                  >
                    {actionLabel ?? "Ego Network"}
                  </button>
                ) : (
                  <a
                    href={`/chat?query=${encodeURIComponent(`Show ego network for ${selectedNode.label}`)}`}
                    className="flex items-center justify-center rounded bg-accent-600 hover:bg-accent-700 text-white px-2 py-1 text-[10px] font-semibold transition text-center"
                  >
                    Ego Network
                  </a>
                )}
                <a
                  href={`/risk?person=${encodeURIComponent(selectedNode.id)}&name=${encodeURIComponent(selectedNode.label)}`}
                  className="flex items-center justify-center rounded bg-amber-50 border border-amber-100 hover:bg-amber-100 dark:bg-amber-950/40 dark:border-amber-900 dark:hover:bg-amber-900/60 px-2 py-1 text-[10px] font-medium text-amber-700 dark:text-amber-300 transition text-center"
                >
                  Risk Profiling
                </a>
                <a
                  href={`/financial?tab=by-person&person=${encodeURIComponent(selectedNode.id)}&name=${encodeURIComponent(selectedNode.label)}`}
                  className="flex items-center justify-center rounded bg-emerald-50 border border-emerald-100 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:border-emerald-900 dark:hover:bg-emerald-900/60 px-2 py-1 text-[10px] font-medium text-emerald-700 dark:text-emerald-300 transition text-center"
                >
                  Scan Financials
                </a>
              </div>
            )}

            {selectedNode.type === "Account" && (
              <div className="space-y-1.5">
                <div className="grid grid-cols-2 gap-1.5">
                  <a
                    href={`/financial?tab=structuring&account=${encodeURIComponent(selectedNode.label)}`}
                    className="flex items-center justify-center rounded bg-emerald-50 border border-emerald-100 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:border-emerald-900 dark:hover:bg-emerald-900/60 px-2 py-1 text-[10px] font-semibold text-emerald-700 dark:text-emerald-300 transition text-center"
                  >
                    Check Structuring
                  </a>
                  <a
                    href={`/financial?tab=funnel&account=${encodeURIComponent(selectedNode.label)}`}
                    className="flex items-center justify-center rounded bg-amber-50 border border-amber-100 hover:bg-amber-100 dark:bg-amber-950/40 dark:border-amber-900 dark:hover:bg-amber-900/60 px-2 py-1 text-[10px] font-semibold text-amber-700 dark:text-amber-300 transition text-center"
                  >
                    Check Funnel/Mule
                  </a>
                </div>
                <a
                  href={`/financial?tab=cycles`}
                  className="flex items-center justify-center w-full rounded bg-zinc-100 border border-zinc-200 hover:bg-zinc-200 dark:bg-zinc-800 dark:border-zinc-700 dark:hover:bg-zinc-700 px-2 py-1 text-[10px] font-medium text-zinc-700 dark:text-zinc-300 transition text-center"
                >
                  Layering Cycles / Clusters Scan
                </a>
              </div>
            )}

            {selectedNode.type === "Incident" && (
              <div className="space-y-1.5">
                <a
                  href={`/cases/${encodeURIComponent(selectedNode.id)}`}
                  className="flex items-center justify-center w-full rounded bg-rose-50 border border-rose-100 hover:bg-rose-100 dark:bg-rose-950/40 dark:border-rose-900 dark:hover:bg-rose-900/60 px-2 py-1 text-[10px] font-semibold text-rose-700 dark:text-rose-300 transition text-center"
                >
                  View Case Workspace
                </a>
                <a
                  href={`/trends`}
                  className="flex items-center justify-center w-full rounded bg-zinc-100 border border-zinc-200 hover:bg-zinc-200 dark:bg-zinc-800 dark:border-zinc-700 dark:hover:bg-zinc-700 px-2 py-1 text-[10px] font-medium text-zinc-700 dark:text-zinc-300 transition text-center"
                >
                  Spatial Hotspots / Forecast Trends
                </a>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Top right spacing & view controls */}
      <div className="absolute right-2 top-2 flex items-center gap-1.5 z-10">
        <button
          type="button"
          onClick={() => setShowAllLabels(!showAllLabels)}
          className={cn(
            "rounded px-2 py-0.5 text-[9px] font-medium transition cursor-pointer select-none border border-zinc-200 dark:border-zinc-800",
            showAllLabels
              ? "bg-accent-600 text-white"
              : "bg-white/90 dark:bg-zinc-900/90 text-zinc-600 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100"
          )}
        >
          {showAllLabels ? "Focus Labels" : "Show All Labels"}
        </button>
        <button
          type="button"
          onClick={() => setSpacious(!spacious)}
          className={cn(
            "rounded px-2 py-0.5 text-[9px] font-medium transition cursor-pointer select-none border border-zinc-200 dark:border-zinc-800",
            spacious
              ? "bg-accent-600 text-white"
              : "bg-white/90 dark:bg-zinc-900/90 text-zinc-600 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100"
          )}
        >
          {spacious ? "Compact view" : "Expand spacing"}
        </button>
        {(transform.k !== 1 || transform.x !== 0 || transform.y !== 0) && (
          <button
            type="button"
            onClick={resetView}
            className="rounded border border-zinc-200 bg-white/90 px-1.5 py-0.5 text-[9px] text-zinc-500 shadow-xs hover:text-zinc-800 dark:border-zinc-700 dark:bg-zinc-900/90 dark:text-zinc-400 dark:hover:text-zinc-100"
          >
            Reset view
          </button>
        )}
      </div>

      {/* Top left entity filter checkboxes */}
      <div className="absolute left-2 top-2 flex items-center gap-2 z-10 bg-white/80 dark:bg-zinc-900/80 p-1.5 rounded-md shadow-xs border border-zinc-200/60 dark:border-zinc-800/60 text-[10px] text-zinc-600 dark:text-zinc-300">
        <span className="font-semibold text-zinc-400 dark:text-zinc-500 mr-0.5 uppercase tracking-wider text-[9px]">FILTER ENTITIES:</span>
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showPersons}
            onChange={() => setShowPersons(!showPersons)}
            className="size-3 rounded accent-indigo-500 cursor-pointer"
          />
          People
        </label>
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showIncidents}
            onChange={() => setShowIncidents(!showIncidents)}
            className="size-3 rounded accent-rose-500 cursor-pointer"
          />
          Incidents
        </label>
        <label className="flex items-center gap-1 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showAccounts}
            onChange={() => setShowAccounts(!showAccounts)}
            className="size-3 rounded accent-emerald-500 cursor-pointer"
          />
          Accounts
        </label>
      </div>

      {/* Bottom legend with Confirmed vs Predicted Link Toggles */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-2.5 pb-2 pt-1 text-[11px] text-zinc-400 bg-zinc-950/20 border-t border-zinc-850">
        <label className="flex items-center gap-1.5 cursor-pointer select-none hover:text-zinc-200 transition">
          <input
            type="checkbox"
            checked={showConfirmedEdges}
            onChange={() => setShowConfirmedEdges(!showConfirmedEdges)}
            className="size-3 rounded accent-zinc-500 cursor-pointer"
          />
          <span className="inline-block h-px w-3 bg-zinc-400 dark:bg-zinc-600 mr-0.5" /> Confirmed Link
        </label>
        <label className="flex items-center gap-1.5 cursor-pointer select-none hover:text-zinc-200 transition">
          <input
            type="checkbox"
            checked={showPredictedEdges}
            onChange={() => setShowPredictedEdges(!showPredictedEdges)}
            className="size-3 rounded accent-caution-500 cursor-pointer"
          />
          <span className="inline-block h-px w-3 border-t border-dashed border-caution-500/60 mr-0.5" /> Predicted — unverified
        </label>
        <span className="ml-auto hidden sm:inline">Scroll to zoom · drag to pan{onNodeSelect ? " · click a node to inspect" : ""}</span>
      </div>
    </div>
  )
}

export { NetworkGraph }
