import * as React from "react"
import { ArrowLeft, Check, Minus, ShieldHalf } from "lucide-react"
import { Link } from "react-router-dom"
import { useTranslation } from "react-i18next"

import {
  ALL_RANKS,
  PERMISSION_GROUPS,
  PERMISSION_LABELS,
  RANK_LABELS,
  RANK_SUMMARIES,
  ROLE_PERMISSIONS,
  roleHasPermission,
} from "@/lib/types/permissions"

/**
 * Public, unauthenticated reference for "who can access what", linked from the
 * sign-in screen. Deliberately reachable without a session: someone deciding
 * whether to request access, or which rank to pick right after signing up,
 * cannot see this if it sits behind the auth guard.
 *
 * Rendered straight from ROLE_PERMISSIONS, the same table the UI gates on, so
 * this page cannot drift from the app's actual behaviour. It still mirrors the
 * server's matrix by hand (see that module's note), so treat this as
 * documentation of intent, not as the enforcement boundary.
 */
function AccessScopePage() {
  const { t } = useTranslation()

  return (
    <div className="min-h-screen bg-zinc-100 dark:bg-zinc-950">
      <div className="mx-auto w-full max-w-6xl px-4 py-10 sm:px-6">
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 text-xs text-zinc-500 transition-colors hover:text-zinc-800 dark:text-zinc-400 dark:hover:text-zinc-100"
        >
          <ArrowLeft className="size-3.5" />
          {t("accessScope.back")}
        </Link>

        <div className="mt-6 flex items-start gap-3">
          <div className="glass-surface flex size-11 shrink-0 items-center justify-center rounded-lg">
            <ShieldHalf className="size-5 text-accent-600 dark:text-accent-300" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("accessScope.title")}</h1>
            <p className="mt-1 max-w-2xl text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
              {t("accessScope.subtitle")}
            </p>
          </div>
        </div>

        <h2 className="section-label mt-10">{t("accessScope.rolesHeading")}</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {ALL_RANKS.map((rank) => (
            <div key={rank} className="glass-surface rounded-lg p-4">
              <div className="flex items-baseline justify-between gap-2">
                <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50">{RANK_LABELS[rank]}</p>
                <span className="shrink-0 text-[11px] tabular-nums text-zinc-400">
                  {t("accessScope.permissionCount", { count: ROLE_PERMISSIONS[rank].length })}
                </span>
              </div>
              <p className="mt-1.5 text-xs leading-relaxed text-zinc-500 dark:text-zinc-400">
                {RANK_SUMMARIES[rank]}
              </p>
            </div>
          ))}
        </div>

        <h2 className="section-label mt-10">{t("accessScope.matrixHeading")}</h2>
        <p className="mt-1 text-xs text-zinc-500 dark:text-zinc-400">{t("accessScope.matrixHint")}</p>

        {/* The matrix is wider than a phone viewport, so it scrolls inside its
            own container rather than making the whole page scroll sideways. */}
        <div className="glass-surface mt-3 overflow-x-auto rounded-lg">
          <table className="w-full min-w-[720px] border-collapse text-left">
            <thead>
              <tr className="border-b border-zinc-200 dark:border-zinc-800">
                <th className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
                  {t("accessScope.capabilityColumn")}
                </th>
                {ALL_RANKS.map((rank) => (
                  <th
                    key={rank}
                    className="px-2 py-3 text-center text-[11px] font-semibold uppercase tracking-wider text-zinc-500"
                  >
                    {RANK_LABELS[rank]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {PERMISSION_GROUPS.map((group) => (
                <React.Fragment key={group.title}>
                  <tr>
                    <td
                      colSpan={ALL_RANKS.length + 1}
                      className="bg-zinc-200/40 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-zinc-500 dark:bg-zinc-800/40 dark:text-zinc-400"
                    >
                      {group.title}
                    </td>
                  </tr>
                  {group.permissions.map((permission) => (
                    <tr key={permission} className="border-t border-zinc-200/60 dark:border-zinc-800/60">
                      <td className="px-4 py-2.5 text-xs text-zinc-700 dark:text-zinc-200">
                        {PERMISSION_LABELS[permission]}
                      </td>
                      {ALL_RANKS.map((rank) => {
                        const granted = roleHasPermission(rank, permission)
                        return (
                          <td key={rank} className="px-2 py-2.5 text-center">
                            {granted ? (
                              <Check
                                className="mx-auto size-3.5 text-accent-600 dark:text-accent-300"
                                aria-label={t("accessScope.granted")}
                              />
                            ) : (
                              <Minus
                                className="mx-auto size-3.5 text-zinc-300 dark:text-zinc-700"
                                aria-label={t("accessScope.notGranted")}
                              />
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <p className="mt-4 max-w-3xl text-[11px] leading-relaxed text-zinc-400 dark:text-zinc-500">
          {t("accessScope.footnote")}
        </p>
      </div>
    </div>
  )
}

export { AccessScopePage }
