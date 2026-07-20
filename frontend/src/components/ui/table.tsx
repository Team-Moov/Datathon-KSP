import * as React from "react"

import { cn } from "@/lib/utils"

/* Compact variant throughout — tighter row padding, smaller type. This is a
   scanning tool for hundreds of case/audit rows, not a marketing page table. */

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div className="relative w-full overflow-x-auto">
      <table className={cn("w-full caption-bottom text-sm", className)} {...props} />
    </div>
  )
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead className={cn("border-b border-zinc-200 dark:border-zinc-800", className)} {...props} />
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody className={cn("divide-y divide-zinc-100 dark:divide-zinc-900", className)} {...props} />
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return (
    <tr
      className={cn("transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-900/60", className)}
      {...props}
    />
  )
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return (
    <th
      className={cn(
        "h-8 whitespace-nowrap px-3 text-left text-[11px] font-semibold uppercase tracking-wider text-zinc-500 dark:text-zinc-400",
        className,
      )}
      {...props}
    />
  )
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return <td className={cn("px-3 py-2 text-zinc-700 dark:text-zinc-300", className)} {...props} />
}

export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell }
