import * as React from "react"
import { QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter } from "react-router-dom"

import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"
import { AuthProvider } from "@/features/auth/AuthProvider"
import { queryClient } from "@/lib/api/queryClient"
import { ThemeProvider } from "./ThemeProvider"

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        {/* import.meta.env.BASE_URL mirrors vite.config.ts's `base` — "/" in
            dev, "/app/" in production builds, since Catalyst Web Client
            Hosting serves the app under that subpath, not the domain root. */}
        <BrowserRouter basename={import.meta.env.BASE_URL}>
          <AuthProvider>
            <TooltipProvider delayDuration={200}>
              {children}
              <Toaster />
            </TooltipProvider>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
