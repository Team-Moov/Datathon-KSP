import { Skeleton } from "@/components/ui/skeleton"

interface LoadingSkeletonProps {
  rows?: number
  variant?: "table" | "card" | "list"
}

function LoadingSkeleton({ rows = 5, variant = "list" }: LoadingSkeletonProps) {
  if (variant === "table") {
    return (
      <div className="space-y-2 p-3">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div key={rowIndex} className="flex gap-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
    )
  }

  if (variant === "card") {
    return (
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: rows }).map((_, cardIndex) => (
          <div key={cardIndex} className="flat-surface space-y-3 rounded-lg p-4">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-6 w-2/3" />
            <Skeleton className="h-3 w-full" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3 p-3">
      {Array.from({ length: rows }).map((_, itemIndex) => (
        <Skeleton key={itemIndex} className="h-4 w-full" />
      ))}
    </div>
  )
}

export { LoadingSkeleton }
