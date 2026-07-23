import * as React from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Database, RefreshCw, Sparkles } from "lucide-react"
import { toast } from "sonner"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import {
  fetchJobStatus,
  triggerEmbeddingBackfill,
  triggerGwrRecompute,
  type JobStatus,
  type JobStatusRecord,
} from "./adminApi"

const TERMINAL_STATUSES: JobStatus[] = ["SUCCESS", "FAILURE"]

const STATUS_BADGE_VARIANT: Record<JobStatus, "neutral" | "accent" | "affirm" | "critical"> = {
  PENDING: "neutral",
  STARTED: "accent",
  RETRY: "accent",
  SUCCESS: "affirm",
  FAILURE: "critical",
}

interface JobCardProps {
  icon: React.ElementType
  title: string
  description: string
  triggerLabel: string
  triggerFn: () => Promise<{ task_id: string; task_name: string }>
}

function JobCard({ icon: Icon, title, description, triggerLabel, triggerFn }: JobCardProps) {
  const [taskId, setTaskId] = React.useState<string | null>(null)

  const triggerMutation = useMutation({
    mutationFn: triggerFn,
    onSuccess: (data) => {
      setTaskId(data.task_id)
      toast.success(`${title} started`)
    },
    onError: (error) => toast.error(extractApiErrorMessage(error)),
  })

  const statusQuery = useQuery<JobStatusRecord>({
    queryKey: ["admin-job-status", taskId],
    queryFn: () => fetchJobStatus(taskId as string),
    enabled: taskId !== null,
    refetchIntervalInBackground: true,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status && TERMINAL_STATUSES.includes(status) ? false : 2000
    },
  })

  React.useEffect(() => {
    if (statusQuery.data?.status === "SUCCESS") {
      toast.success(`${title} finished`)
    } else if (statusQuery.data?.status === "FAILURE") {
      toast.error(`${title} failed: ${statusQuery.data.error ?? "unknown error"}`)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusQuery.data?.status])

  const isRunning = taskId !== null && !TERMINAL_STATUSES.includes(statusQuery.data?.status as JobStatus)

  return (
    <Card>
      <CardHeader className="flex flex-row items-start justify-between gap-3 space-y-0">
        <div className="flex gap-3">
          <Icon className="mt-0.5 size-4 shrink-0 text-zinc-400" />
          <div>
            <CardTitle>{title}</CardTitle>
            <CardDescription>{description}</CardDescription>
          </div>
        </div>
        {statusQuery.data ? <Badge variant={STATUS_BADGE_VARIANT[statusQuery.data.status]}>{statusQuery.data.status.toLowerCase()}</Badge> : null}
      </CardHeader>
      <CardContent className="flex items-center justify-between gap-3">
        <p className="text-xs text-zinc-500">
          {taskId
            ? `Task ${taskId.slice(0, 8)}…${
                statusQuery.data?.result
                  ? ` — ${Object.entries(statusQuery.data.result)
                      .map(([k, v]) => `${k}: ${v}`)
                      .join(", ")}`
                  : ""
              }`
            : "Not run yet this session."}
        </p>
        <Button
          size="sm"
          variant="outline"
          className="shrink-0 gap-1.5"
          onClick={() => triggerMutation.mutate()}
          disabled={triggerMutation.isPending || isRunning}
        >
          <RefreshCw className={`size-3.5 ${isRunning ? "animate-spin" : ""}`} />
          {isRunning ? "Running…" : triggerLabel}
        </Button>
      </CardContent>
    </Card>
  )
}

function SystemJobsPage() {
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">System Jobs</h1>
        <p className="text-sm text-zinc-500">
          On-demand triggers for batch analytics jobs. GWR also recomputes automatically on a weekly
          schedule; embeddings are generated automatically for every newly ingested document — these
          buttons are for backfills and "don't want to wait for the schedule."
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <JobCard
          icon={Sparkles}
          title="Recompute GWR"
          description="Re-fit geographically weighted regression coefficients across all qualifying districts."
          triggerLabel="Recompute now"
          triggerFn={triggerGwrRecompute}
        />
        <JobCard
          icon={Database}
          title="Backfill Embeddings"
          description="Embed any case narratives that predate the automatic embed-on-ingest path."
          triggerLabel="Backfill now"
          triggerFn={triggerEmbeddingBackfill}
        />
      </div>
    </div>
  )
}

export { SystemJobsPage }
