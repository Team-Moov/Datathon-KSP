import * as React from "react"
import { useMutation, useQuery } from "@tanstack/react-query"
import { Banknote } from "lucide-react"
import { useSearchParams } from "react-router-dom"
import { useTranslation } from "react-i18next"

import { EmptyState } from "@/components/data-states/EmptyState"
import { ErrorState } from "@/components/data-states/ErrorState"
import { LoadingSkeleton } from "@/components/data-states/LoadingSkeleton"
import { FinancialAlertCard } from "@/components/charts/FinancialAlertCard"
import { PersonPicker, type PickedPerson } from "@/components/inputs/PersonPicker"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { cn } from "@/lib/utils"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import {
  detectFunnelAccount,
  detectLayeringCycles,
  detectOrganizedClusters,
  detectStructuring,
  fetchPersonAccounts,
  runFullScan,
  type SuspiciousTransactionAlert,
} from "./financialApi"

function parseAccountList(raw: string): string[] {
  return Array.from(new Set(raw.split(/[\n,]/).map((entry) => entry.trim()).filter(Boolean)))
}

function AccountLookupTab({ detect }: { detect: (account: string) => Promise<SuspiciousTransactionAlert | null> }) {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const accountParam = searchParams.get("account") || ""
  const [account, setAccount] = React.useState(accountParam)
  const mutation = useMutation({ mutationFn: () => detect(account.trim()) })

  React.useEffect(() => {
    if (accountParam) {
      setAccount(accountParam)
      mutation.mutate()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountParam])

  return (
    <div className="space-y-4">
      <div className="flex items-end gap-3">
        <Input value={account} onChange={(event) => setAccount(event.target.value)} placeholder={t("financial.accountIdentifier")} className="flex-1" />
        <Button onClick={() => mutation.mutate()} disabled={!account.trim() || mutation.isPending}>
          {mutation.isPending ? t("financial.checking") : t("financial.checkAccount")}
        </Button>
      </div>
      {mutation.isError ? <p className="text-xs text-critical-500">{extractApiErrorMessage(mutation.error)}</p> : null}
      {mutation.isSuccess && !mutation.data ? (
        <EmptyState title={t("financial.noAlertTriggered")} description={t("financial.noAlertTriggeredDesc")} />
      ) : null}
      {mutation.data ? <FinancialAlertCard alert={mutation.data} /> : null}
    </div>
  )
}

function MultiAccountTab({
  run,
  placeholder,
  buttonLabel,
  emptyDescription,
}: {
  run: (accounts: string[]) => Promise<SuspiciousTransactionAlert[]>
  placeholder: string
  buttonLabel: string
  emptyDescription: string
}) {
  const { t } = useTranslation()
  const [accountsText, setAccountsText] = React.useState("")
  const accounts = parseAccountList(accountsText)
  const mutation = useMutation({ mutationFn: () => run(accounts) })

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <textarea
          value={accountsText}
          onChange={(event) => setAccountsText(event.target.value)}
          placeholder={placeholder}
          rows={3}
          className="w-full rounded-md border border-zinc-300 bg-white p-2.5 text-sm text-zinc-900 outline-none focus-visible:border-accent-400 focus-visible:ring-2 focus-visible:ring-accent-400/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <div className="flex items-center justify-between">
          <span className="text-xs text-zinc-400">{t("financial.accountCount", { count: accounts.length })}</span>
          <Button onClick={() => mutation.mutate()} disabled={accounts.length === 0 || mutation.isPending}>
            {mutation.isPending ? t("financial.running") : buttonLabel}
          </Button>
        </div>
      </div>
      {mutation.isError ? <p className="text-xs text-critical-500">{extractApiErrorMessage(mutation.error)}</p> : null}
      {mutation.isSuccess && mutation.data.length === 0 ? <EmptyState title={t("financial.noAlerts")} description={emptyDescription} /> : null}
      {mutation.data && mutation.data.length > 0 ? (
        <div className="space-y-3">
          {mutation.data.map((alert, index) => (
            <FinancialAlertCard key={index} alert={alert} />
          ))}
        </div>
      ) : null}
    </div>
  )
}

function CyclesTab() {
  const { t } = useTranslation()
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ["financial-cycles"],
    queryFn: detectLayeringCycles,
  })

  if (isLoading) return <LoadingSkeleton variant="card" rows={2} />
  if (isError) return <ErrorState message={extractApiErrorMessage(error)} onRetry={() => void refetch()} />
  if (!data || data.length === 0) return <EmptyState icon={Banknote} title={t("financial.noLayeringCycles")} />

  return (
    <div className="space-y-3">
      {data.map((alert, index) => (
        <FinancialAlertCard key={index} alert={alert} />
      ))}
    </div>
  )
}

/** Start from a person, not an opaque account: pick a person → see their linked
 * accounts → scan them in one click. Supports a ?person= deep link from the person
 * page / chat / an alert. */
function ByPersonTab() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const [selected, setSelected] = React.useState<PickedPerson | null>(null)

  const hydratedRef = React.useRef(false)
  React.useEffect(() => {
    if (hydratedRef.current) return
    hydratedRef.current = true
    const personId = searchParams.get("person")
    if (personId) setSelected({ id: personId, name: searchParams.get("name") || t("network.selectedPerson") })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function selectPerson(person: PickedPerson) {
    setSelected(person)
    setSearchParams((prev) => {
      prev.set("person", person.id)
      prev.set("name", person.name)
      return prev
    })
  }
  function clearPerson() {
    setSelected(null)
    setSearchParams((prev) => {
      prev.delete("person")
      prev.delete("name")
      return prev
    })
  }

  const accountsQuery = useQuery({
    queryKey: ["person-accounts", selected?.id],
    queryFn: () => fetchPersonAccounts(selected!.id),
    enabled: Boolean(selected),
  })

  const scanMutation = useMutation({
    mutationFn: (accounts: string[]) => runFullScan(accounts),
  })

  const accounts = accountsQuery.data ?? []

  return (
    <div className="space-y-4">
      <div className="w-full max-w-sm space-y-1">
        <p className="section-label">{t("financial.person")}</p>
        <PersonPicker selected={selected} onSelect={selectPerson} onClear={clearPerson} />
      </div>

      {!selected ? (
        <EmptyState icon={Banknote} title={t("financial.pickPerson")} description={t("financial.pickPersonDesc")} />
      ) : accountsQuery.isLoading ? (
        <LoadingSkeleton variant="list" rows={3} />
      ) : accountsQuery.isError ? (
        <ErrorState message={extractApiErrorMessage(accountsQuery.error)} onRetry={() => void accountsQuery.refetch()} />
      ) : accounts.length === 0 ? (
        <EmptyState title={t("financial.noLinkedAccounts")} description={t("financial.noLinkedAccountsDesc")} />
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-400">
              {t("financial.linkedAccountsCount", { count: accounts.length })}
            </span>
            <Button
              onClick={() => scanMutation.mutate(accounts.map((a) => a.account))}
              disabled={scanMutation.isPending}
            >
              {scanMutation.isPending ? t("financial.scanning") : t("financial.scanAllAccounts")}
            </Button>
          </div>
          <ul className="flat-surface divide-y divide-zinc-100 rounded-md dark:divide-zinc-900">
            {accounts.map((entry) => (
              <li key={entry.account} className="flex items-center justify-between px-3 py-2 text-sm">
                <span className="font-mono text-zinc-700 dark:text-zinc-200">{entry.account}</span>
                <span className="flex items-center gap-2 text-xs text-zinc-400">
                  <span>{t("financial.txnCount", { count: entry.txn_count })}</span>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px]",
                      entry.flagged
                        ? "bg-caution-500/15 text-caution-600 dark:text-caution-500"
                        : "bg-zinc-100 text-zinc-400 dark:bg-zinc-800",
                    )}
                  >
                    {entry.flagged ? t("financial.flagged") : t("financial.clean")}
                  </span>
                </span>
              </li>
            ))}
          </ul>
          {scanMutation.isError ? (
            <p className="text-xs text-critical-500">{extractApiErrorMessage(scanMutation.error)}</p>
          ) : null}
          {scanMutation.isSuccess && scanMutation.data.length === 0 ? (
            <EmptyState title={t("financial.noAlerts")} description={t("financial.noTypologyMatchedPerson")} />
          ) : null}
          {scanMutation.data && scanMutation.data.length > 0 ? (
            <div className="space-y-3">
              {scanMutation.data.map((alert, index) => (
                <FinancialAlertCard key={index} alert={alert} />
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  )
}

function FinancialCrimePage() {
  const { t } = useTranslation()
  const [searchParams, setSearchParams] = useSearchParams()
  const activeTab = searchParams.get("tab") || "by-person"

  function handleTabChange(value: string) {
    setSearchParams((prev) => {
      prev.set("tab", value)
      return prev
    })
  }

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">{t("financial.title")}</h1>

      <Card>
        <CardHeader>
          <CardTitle>{t("financial.subtitle")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs value={activeTab} onValueChange={handleTabChange}>
            <TabsList>
              <TabsTrigger value="by-person">{t("financial.tabs.byPerson")}</TabsTrigger>
              <TabsTrigger value="structuring">{t("financial.tabs.structuring")}</TabsTrigger>
              <TabsTrigger value="funnel">{t("financial.tabs.funnel")}</TabsTrigger>
              <TabsTrigger value="cycles">{t("financial.tabs.cycles")}</TabsTrigger>
              <TabsTrigger value="clusters">{t("financial.tabs.clusters")}</TabsTrigger>
              <TabsTrigger value="scan">{t("financial.tabs.scan")}</TabsTrigger>
            </TabsList>
            <TabsContent value="by-person">
              <ByPersonTab />
            </TabsContent>
            <TabsContent value="structuring">
              <AccountLookupTab detect={detectStructuring} />
            </TabsContent>
            <TabsContent value="funnel">
              <AccountLookupTab detect={detectFunnelAccount} />
            </TabsContent>
            <TabsContent value="cycles">
              <CyclesTab />
            </TabsContent>
            <TabsContent value="clusters">
              <MultiAccountTab
                run={detectOrganizedClusters}
                placeholder={t("financial.clustersPlaceholder")}
                buttonLabel={t("financial.detectClusters")}
                emptyDescription={t("financial.noClusterFound")}
              />
            </TabsContent>
            <TabsContent value="scan">
              <MultiAccountTab
                run={runFullScan}
                placeholder={t("financial.scanPlaceholder")}
                buttonLabel={t("financial.runFullScan")}
                emptyDescription={t("financial.noTypologyMatched")}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

export { FinancialCrimePage }
