import type { LucideIcon } from "lucide-react"
import { Inbox } from "lucide-react"

import { Button } from "@/components/ui/button"

interface EmptyStateProps {
  icon?: LucideIcon
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}

function EmptyState({ icon: Icon = Inbox, title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <Icon className="size-8 text-zinc-300 dark:text-zinc-700" strokeWidth={1.5} />
      <p className="text-sm font-medium text-zinc-600 dark:text-zinc-300">{title}</p>
      {description ? <p className="max-w-sm text-xs text-zinc-400 dark:text-zinc-500">{description}</p> : null}
      {actionLabel && onAction ? (
        <Button variant="outline" size="sm" className="mt-2" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  )
}

export { EmptyState }
