import * as React from "react"
import { ChevronsLeft, ChevronsRight, ShieldHalf } from "lucide-react"
import { NavLink } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { usePermission } from "@/lib/hooks/usePermission"
import { cn } from "@/lib/utils"
import { NAVIGATION_GROUPS } from "./navigationConfig"

const SIDEBAR_COLLAPSED_STORAGE_KEY = "ksp.sidebarCollapsed"

function Sidebar() {
  const { t } = useTranslation()
  const [isCollapsed, setIsCollapsed] = React.useState(
    () => localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === "true",
  )
  const { has } = usePermission()

  function toggleCollapsed() {
    setIsCollapsed((previous) => {
      const next = !previous
      localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(next))
      return next
    })
  }

  return (
    <aside
      className={cn(
        "glass-surface sticky top-0 flex h-screen shrink-0 flex-col transition-[width] duration-150",
        isCollapsed ? "w-16" : "w-60",
      )}
    >
      <div className="flex h-14 items-center gap-2 border-b border-zinc-200 px-4 dark:border-zinc-800">
        <ShieldHalf className="size-5 shrink-0 text-accent-600 dark:text-accent-300" />
        {!isCollapsed ? (
          <span className="truncate text-sm font-semibold text-zinc-800 dark:text-zinc-100">
            {t("nav.appName")}
          </span>
        ) : null}
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {NAVIGATION_GROUPS.map((group) => {
          const visibleEntries = group.entries.filter(
            (entry) => !entry.requiredPermission || has(entry.requiredPermission),
          )
          if (visibleEntries.length === 0) return null

          return (
            <div key={group.labelKey} className="mb-4">
              {!isCollapsed ? <p className="section-label mb-1.5 px-2">{t(group.labelKey)}</p> : null}
              <ul className="space-y-0.5">
                {visibleEntries.map((entry) => (
                  <li key={entry.path}>
                    <NavLink
                      to={entry.path}
                      end={entry.path === "/"}
                      className={({ isActive }) =>
                        cn(
                          "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                          isActive
                            ? "bg-accent-50 font-medium text-accent-800 dark:bg-accent-900/40 dark:text-accent-100"
                            : "text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800/60",
                        )
                      }
                    >
                      <entry.icon className="size-4 shrink-0" />
                      {!isCollapsed ? <span className="truncate">{t(entry.labelKey)}</span> : null}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          )
        })}
      </nav>

      <button
        type="button"
        onClick={toggleCollapsed}
        className="flex h-10 items-center justify-center border-t border-zinc-200 text-zinc-500 transition-colors hover:bg-zinc-100 dark:border-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800/60"
      >
        {isCollapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
      </button>
    </aside>
  )
}

export { Sidebar }
