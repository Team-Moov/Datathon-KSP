import { Info } from "lucide-react"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

interface MetricWithInfoProps {
  label: string
  value: string | number
  info: string
  valueClassName?: string
  labelClassName?: string
}

export function MetricWithInfo({
  label,
  value,
  info,
  valueClassName = "text-lg font-bold text-accent-600 dark:text-accent-400",
  labelClassName = "text-[11px] font-medium text-zinc-500 dark:text-zinc-400",
}: MetricWithInfoProps) {
  return (
    <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 shadow-sm space-y-1">
      <div className="flex items-center gap-1.5">
        <span className={labelClassName}>{label}</span>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <button className="inline-flex text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors">
                <Info className="w-3.5 h-3.5" />
              </button>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <p className="text-xs">{info}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
      <div className={valueClassName}>{value}</div>
    </div>
  )
}
