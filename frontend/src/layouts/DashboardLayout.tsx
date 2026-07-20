import { Outlet } from "react-router-dom"

import { Sidebar } from "./Sidebar"
import { TopHeader } from "./TopHeader"

function DashboardLayout() {
  return (
    <div className="flex min-h-screen bg-zinc-100 dark:bg-zinc-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopHeader />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

export { DashboardLayout }
