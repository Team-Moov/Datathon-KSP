import { ChevronRight } from "lucide-react"
import { Link, useLocation } from "react-router-dom"

const SEGMENT_LABELS: Record<string, string> = {
  cases: "Cases",
  persons: "Persons",
  network: "Network Explorer",
  risk: "Risk Profiling",
  financial: "Financial Crime",
  trends: "Trends & Forecasting",
  socio: "Sociological Insights",
  chat: "Assistant",
  admin: "Governance",
  "audit-log": "Audit Log",
  users: "User Management",
}

function labelForSegment(segment: string): string {
  if (SEGMENT_LABELS[segment]) return SEGMENT_LABELS[segment]
  // Route params (a UUID or crime number) — show a shortened form rather than
  // the raw identifier so the breadcrumb bar doesn't overflow.
  if (segment.length > 14) return `${segment.slice(0, 8)}...`
  return segment
}

function Breadcrumbs() {
  const location = useLocation()
  const segments = location.pathname.split("/").filter(Boolean)

  if (segments.length === 0) {
    return <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200">Overview</p>
  }

  return (
    <nav className="flex items-center gap-1 text-sm">
      <Link to="/" className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300">
        Overview
      </Link>
      {segments.map((segment, index) => {
        const path = `/${segments.slice(0, index + 1).join("/")}`
        const isLast = index === segments.length - 1
        return (
          <span key={path} className="flex items-center gap-1">
            <ChevronRight className="size-3.5 text-zinc-300 dark:text-zinc-700" />
            {isLast ? (
              <span className="font-medium text-zinc-800 dark:text-zinc-100">{labelForSegment(segment)}</span>
            ) : (
              <Link to={path} className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300">
                {labelForSegment(segment)}
              </Link>
            )}
          </span>
        )
      })}
    </nav>
  )
}

export { Breadcrumbs }
