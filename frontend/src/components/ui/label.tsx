import * as React from "react"
import * as LabelPrimitive from "@radix-ui/react-label"

import { cn } from "@/lib/utils"

function Label({ className, ...props }: React.ComponentProps<typeof LabelPrimitive.Root>) {
  return (
    <LabelPrimitive.Root
      className={cn(
        "text-xs font-medium text-zinc-600 peer-disabled:cursor-not-allowed peer-disabled:opacity-50 dark:text-zinc-400",
        className,
      )}
      {...props}
    />
  )
}

export { Label }
