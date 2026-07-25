import { LogOut, Moon, Sun, SunMoon } from "lucide-react"
import { useNavigate } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { LanguageSwitcher } from "@/components/ui/LanguageSwitcher"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useTheme } from "@/app/ThemeProvider"
import { useAuth } from "@/features/auth/AuthProvider"
import { RANK_LABELS } from "@/lib/types/permissions"
import { Breadcrumbs } from "./Breadcrumbs"
import { GlobalPersonSearch } from "./GlobalPersonSearch"

function initialsFromFullName(fullName: string): string {
  const parts = fullName.trim().split(/\s+/)
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}

function ThemeToggle() {
  const { t } = useTranslation()
  const { themePreference, setThemePreference } = useTheme()

  const nextPreference = themePreference === "light" ? "dark" : themePreference === "dark" ? "system" : "light"
  const Icon = themePreference === "light" ? Sun : themePreference === "dark" ? Moon : SunMoon

  return (
    <button
      type="button"
      onClick={() => setThemePreference(nextPreference)}
      className="flex size-8 items-center justify-center rounded-md text-zinc-500 transition-colors hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
      title={t("common.theme", { theme: themePreference })}
    >
      <Icon className="size-4" />
    </button>
  )
}

function TopHeader() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { currentUser, endSession } = useAuth()

  async function initiateSignOut() {
    await endSession()
    navigate("/login", { replace: true })
  }

  return (
    <header className="glass-surface sticky top-0 z-30 flex h-14 items-center justify-between gap-4 px-4">
      <Breadcrumbs />

      <div className="flex items-center gap-3">
        <GlobalPersonSearch />
        <LanguageSwitcher />
        <ThemeToggle />

        {currentUser ? (
          <DropdownMenu>
            <DropdownMenuTrigger className="flex items-center gap-2 rounded-md py-1 pl-1 pr-2 outline-none transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800">
              <Avatar className="size-7">
                <AvatarFallback>{initialsFromFullName(currentUser.full_name)}</AvatarFallback>
              </Avatar>
              <div className="hidden text-left sm:block">
                <p className="text-xs font-medium leading-tight text-zinc-800 dark:text-zinc-100">
                  {currentUser.full_name}
                </p>
                <p className="text-[11px] leading-tight text-zinc-500 dark:text-zinc-400">
                  {RANK_LABELS[currentUser.role]}
                </p>
              </div>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuLabel>{currentUser.email}</DropdownMenuLabel>
              <div className="px-2 pb-1.5">
                <Badge variant="accent">{RANK_LABELS[currentUser.role]}</Badge>
                {currentUser.badge_number ? (
                  <span className="ml-1.5 text-[11px] text-zinc-400">{currentUser.badge_number}</span>
                ) : null}
              </div>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => void initiateSignOut()} className="gap-2 text-critical-600">
                <LogOut className="size-3.5" />
                {t("common.signOut")}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ) : null}
      </div>
    </header>
  )
}

export { TopHeader }
