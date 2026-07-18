import * as React from "react"

import { cn } from "@/lib/utils"

/* The shared chrome surface — sidebar, top header, panel headers. Translucent
   with a hairline border and a faint top highlight; deliberately no blur (see
   src/styles/globals.css for why). Keep this out of high-density data regions —
   use flat-surface (Card body) there instead. */
function GlassPanel({ className, ...props }: React.ComponentProps<"div">) {
  return <div className={cn("glass-surface", className)} {...props} />
}

export { GlassPanel }
