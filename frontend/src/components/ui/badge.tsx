import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-4",
  {
    variants: {
      variant: {
        neutral: "border-zinc-300 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
        accent: "border-accent-300 bg-accent-50 text-accent-700 dark:border-accent-700 dark:bg-accent-900/40 dark:text-accent-200",
        caution: "border-caution-500/40 bg-caution-500/10 text-caution-600 dark:text-caution-500",
        critical: "border-critical-500/40 bg-critical-500/10 text-critical-600 dark:text-critical-500",
        affirm: "border-affirm-500/40 bg-affirm-500/10 text-affirm-600 dark:text-affirm-500",
      },
    },
    defaultVariants: {
      variant: "neutral",
    },
  },
)

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, className }))} {...props} />
}

export { Badge, badgeVariants }
