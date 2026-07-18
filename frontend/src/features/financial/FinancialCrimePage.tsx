import * as React from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Banknote } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { FinancialFlowDiagram } from "@/components/charts/FinancialFlowDiagram"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { detectFunnelAccount, detectLayeringCycles, detectStructuring, type SuspiciousTransactionAlert } from "./financialApi"

function AlertCard({ alert }: { alert: SuspiciousTransactionAlert }) {
  return (
    <div className="flat-surface space-y-3 rounded-md p-4">
      <div className="flex items-center justify-between">
        <Badge variant="critical">{alert.typology}</Badge>
        <span className="text-xs text-zinc-500">{Math.round(alert.confidence * 100)}% confidence</span>
      </div>
      <FinancialFlowDiagram accountsInvolved={alert.accounts_involved} />
      <dl className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
        {Object.entries(alert.evidence_trail).map(([key, value]) => (
          <div key={key}>
            <dt className="text-zinc-400">{key.replace(/_/g, " ")}</dt>
            <dd className="text-zinc-700 dark:text-zinc-300">{String(value)}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs font-medium text-zinc-600 dark:text-zinc-300">{alert.recommended_action}</p>
      <p className="text-[11px] italic text-zinc-400 dark:text-zinc-600">{alert.disclaimer}</p>
    </div>
  )
}

function AccountLookupTab({ detect }: { detect: (account: string) => Promise<SuspiciousTransactionAlert | null> }) {
  const [account, setAccount] = React.useState("")
  const mutation = useMutation({ mutationFn: () => detect(account.trim()) })

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <Input value={account} onChange={(event) => setAccount(event.target.value)} placeholder="Account identifier" className="flex-1" />
        <Button onClick={() => mutation.mutate()} disabled={!account.trim() || mutation.isPending}>
          {mutation.isPending ? "Checking..." : "Check account"}
        </Button>
      </div>
      {mutation.isError ? <p className="text-xs text-critical-500">{extractApiErrorMessage(mutation.error)}</p> : null}
      {mutation.isSuccess && !mutation.data ? (
        <EmptyState title="No alert triggered" description="This account doesn't match a known typology pattern." />
      ) : null}
      {mutation.data ? <AlertCard alert={mutation.data} /> : null}
    </div>
  )
}

function CyclesTab() {
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["financial-cycles"],
    queryFn: detectLayeringCycles,
  })

  if (isLoading) return <LoadingSkeleton variant="card" rows={2} />
  if (isError) return <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
  if (!data || data.length === 0) return <EmptyState icon={Banknote} title="No layering cycles detected" />

  return (
    <div className="space-y-3">
      {data.map((alert, index) => (
        <AlertCard key={index} alert={alert} />
      ))}
    </div>
  )
}

function FinancialCrimePage() {
  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Financial Crime Detection</h1>

      <Card>
        <CardHeader>
          <CardTitle>Transaction Typology Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="structuring">
            <TabsList>
              <TabsTrigger value="structuring">Structuring</TabsTrigger>
              <TabsTrigger value="funnel">Funnel Account</TabsTrigger>
              <TabsTrigger value="cycles">Layering Cycles</TabsTrigger>
            </TabsList>
            <TabsContent value="structuring">
              <AccountLookupTab detect={detectStructuring} />
            </TabsContent>
            <TabsContent value="funnel">
              <AccountLookupTab detect={detectFunnelAccount} />
            </TabsContent>
            <TabsContent value="cycles">
              <CyclesTab />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

export { FinancialCrimePage }
