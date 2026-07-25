import { AlertTriangle, RefreshCcw } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"

interface ErrorStateProps {
  title?: string
  message: string
  onRetry?: () => void
}

/* Structured error display — every data-fetching hook in this app surfaces a
   typed error object here rather than a generic toast, so the investigator
   knows exactly what failed (permission, network, AI outage) and whether
   retrying makes sense. */
function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <AlertTriangle className="size-8 text-critical-500" strokeWidth={1.5} />
      <p className="text-sm font-medium text-zinc-700 dark:text-zinc-200">{title ?? t("common.couldntLoadThis")}</p>
      <p className="max-w-sm text-xs text-zinc-400 dark:text-zinc-500">{message}</p>
      {onRetry ? (
        <Button variant="outline" size="sm" className="mt-2 gap-1.5" onClick={onRetry}>
          <RefreshCcw className="size-3.5" />
          {t("common.retry")}
        </Button>
      ) : null}
    </div>
  )
}

export { ErrorState }
