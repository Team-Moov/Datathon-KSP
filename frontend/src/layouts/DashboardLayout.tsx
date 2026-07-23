import { Outlet, useLocation } from "react-router-dom"

import { RouteErrorBoundary } from "@/app/RouteErrorBoundary"
import { Sidebar } from "./Sidebar"
import { TopHeader } from "./TopHeader"

function DashboardLayout() {
  const location = useLocation()
  return (
    <div className="flex min-h-screen bg-zinc-100 dark:bg-zinc-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6">
          {/* Keyed by pathname so navigating away from a crashed page resets the boundary. */}
          <RouteErrorBoundary key={location.pathname}>
            <Outlet />
          </RouteErrorBoundary>
        </main>
      </div>
    </div>
  )
}

export { DashboardLayout }
