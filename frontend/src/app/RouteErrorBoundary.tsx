import * as React from "react"
import { AlertTriangle } from "lucide-react"

import { Button } from "@/components/ui/button"

interface RouteErrorBoundaryState {
  error: Error | null
}

/**
 * A render crash inside one page (e.g. a widget given a malformed payload)
 * previously took the whole app blank — no error boundary existed anywhere,
 * so React unmounted all the way to the root. This scopes the blast radius
 * to the routed page content, keeping the sidebar/header alive, and resets
 * automatically on navigation (keyed by pathname in router.tsx) so a broken
 * page doesn't stay stuck once the user moves on.
 */
class RouteErrorBoundary extends React.Component<React.PropsWithChildren, RouteErrorBoundaryState> {
  state: RouteErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): RouteErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("Route render error:", error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flat-surface flex flex-col items-center gap-3 rounded-lg p-8 text-center">
          <AlertTriangle className="size-8 text-critical-500" />
          <p className="text-sm font-medium text-zinc-800 dark:text-zinc-100">This page hit an error and couldn't render.</p>
          <p className="max-w-md text-xs text-zinc-500 dark:text-zinc-400">{this.state.error.message}</p>
          <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}

export { RouteErrorBoundary }
