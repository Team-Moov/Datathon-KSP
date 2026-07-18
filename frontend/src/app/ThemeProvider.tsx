import * as React from "react"

type ThemePreference = "light" | "dark" | "system"
type ResolvedTheme = "light" | "dark"

const THEME_STORAGE_KEY = "ksp.themePreference"
const SYSTEM_DARK_QUERY = "(prefers-color-scheme: dark)"

interface ThemeContextValue {
  themePreference: ThemePreference
  setThemePreference: (preference: ThemePreference) => void
}

const ThemeContext = React.createContext<ThemeContextValue | null>(null)

function resolveSystemTheme(): ResolvedTheme {
  return window.matchMedia(SYSTEM_DARK_QUERY).matches ? "dark" : "light"
}

/**
 * Always stamps an explicit light/dark value onto <html data-theme>, even for
 * "system" — Tailwind's dark: variant is configured (globals.css) to key off
 * this attribute only, not prefers-color-scheme directly, so leaving the
 * attribute unset for "system" would desync the two and produce mismatched
 * surfaces (this was caught visually: a dark glass card on a light page).
 */
function applyResolvedTheme(preference: ThemePreference) {
  const resolved: ResolvedTheme = preference === "system" ? resolveSystemTheme() : preference
  document.documentElement.setAttribute("data-theme", resolved)
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [themePreference, setThemePreferenceState] = React.useState<ThemePreference>(() => {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return stored === "light" || stored === "dark" ? stored : "system"
  })

  React.useEffect(() => {
    applyResolvedTheme(themePreference)
    if (themePreference !== "system") return

    const mediaQuery = window.matchMedia(SYSTEM_DARK_QUERY)
    const handleSystemChange = () => applyResolvedTheme("system")
    mediaQuery.addEventListener("change", handleSystemChange)
    return () => mediaQuery.removeEventListener("change", handleSystemChange)
  }, [themePreference])

  const setThemePreference = React.useCallback((preference: ThemePreference) => {
    setThemePreferenceState(preference)
    localStorage.setItem(THEME_STORAGE_KEY, preference)
  }, [])

  const value = React.useMemo(() => ({ themePreference, setThemePreference }), [themePreference, setThemePreference])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme(): ThemeContextValue {
  const context = React.useContext(ThemeContext)
  if (!context) throw new Error("useTheme must be used within a ThemeProvider")
  return context
}
