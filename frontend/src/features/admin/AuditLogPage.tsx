import * as React from "react"
import { useQuery } from "@tanstack/react-query"
import { ScrollText } from "lucide-react"
import { useTranslation } from "react-i18next"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { useDebouncedValue } from "@/lib/hooks/useDebounce"
import { fetchAuditLog } from "./adminApi"

function AuditLogPage() {
  const { t } = useTranslation()
  const [actionFilter, setActionFilter] = React.useState("")
  const debouncedActionFilter = useDebouncedValue(actionFilter, 300)

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["admin-audit-log", debouncedActionFilter],
    queryFn: () => fetchAuditLog({ action: debouncedActionFilter || undefined, limit: 200 }),
  })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("nav.auditLog")}</h1>
        <Input
          value={actionFilter}
          onChange={(event) => setActionFilter(event.target.value)}
          placeholder={t("auditLog.filterPlaceholder")}
          className="w-72"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t("auditLog.activity")}</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <LoadingSkeleton variant="table" rows={10} />
          ) : isError ? (
            <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
          ) : !data || data.length === 0 ? (
            <EmptyState icon={ScrollText} title={t("auditLog.noMatchingActivity")} />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("auditLog.timestamp")}</TableHead>
                  <TableHead>{t("auditLog.action")}</TableHead>
                  <TableHead>{t("auditLog.resource")}</TableHead>
                  <TableHead>{t("auditLog.user")}</TableHead>
                  <TableHead>{t("auditLog.ipAddress")}</TableHead>
                  <TableHead>{t("auditLog.reason")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.map((entry) => (
                  <TableRow key={entry.id}>
                    <TableCell className="whitespace-nowrap text-xs">{new Date(entry.created_at).toLocaleString()}</TableCell>
                    <TableCell className="font-mono text-xs">{entry.action}</TableCell>
                    <TableCell className="text-xs">
                      {entry.resource_type}
                      {entry.resource_id ? `:${entry.resource_id.slice(0, 8)}` : ""}
                    </TableCell>
                    <TableCell className="font-mono text-xs">{entry.user_id ? entry.user_id.slice(0, 8) : "-"}</TableCell>
                    <TableCell className="text-xs">{entry.ip_address ?? "-"}</TableCell>
                    <TableCell className="text-xs text-zinc-500">{entry.reason ?? "-"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export { AuditLogPage }
