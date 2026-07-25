import * as React from "react"
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Pencil } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { usePermission } from "@/lib/hooks/usePermission"
import type { CaseWorkspaceSnapshot } from "@/lib/types/api"
import { submitCaseUpdate } from "../casesApi"
import { isVersionConflict, workspaceQueryKey } from "../useCaseWorkspace"

interface CaseHeaderCardProps {
  caseId: string
  caseData: CaseWorkspaceSnapshot["case"]
}

function CaseHeaderCard({ caseId, caseData }: CaseHeaderCardProps) {
  const { t } = useTranslation()
  const { has } = usePermission()
  const queryClient = useQueryClient()
  const [isEditOpen, setIsEditOpen] = React.useState(false)
  const [draftBriefFacts, setDraftBriefFacts] = React.useState(caseData.brief_facts ?? "")
  const [conflictMessage, setConflictMessage] = React.useState<string | null>(null)

  React.useEffect(() => {
    setDraftBriefFacts(caseData.brief_facts ?? "")
  }, [caseData.brief_facts])

  const updateMutation = useMutation({
    mutationFn: () => submitCaseUpdate(caseId, { version: caseData.version, brief_facts: draftBriefFacts }),
    onSuccess: () => {
      setIsEditOpen(false)
      void queryClient.invalidateQueries({ queryKey: workspaceQueryKey(caseId) })
    },
    onError: (error) => {
      if (isVersionConflict(error)) {
        setConflictMessage(t("caseHeader.versionConflict"))
        void queryClient.invalidateQueries({ queryKey: workspaceQueryKey(caseId) })
        return
      }
      setConflictMessage(extractApiErrorMessage(error))
    },
  })

  return (
    <Card>
      <CardContent className="flex flex-wrap items-start justify-between gap-4 p-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <h1 className="font-mono text-base font-semibold text-zinc-900 dark:text-zinc-50">{caseData.crime_no}</h1>
            {caseData.disposition ? <Badge variant="neutral">{caseData.disposition}</Badge> : null}
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            {t("caseHeader.reportedOn", { date: caseData.date_reported ?? t("caseHeader.dateUnknown") })} ·{" "}
            {t("common.district")} {caseData.district_id ?? "—"}
          </p>
          {caseData.brief_facts ? (
            <p className="max-w-2xl text-sm text-zinc-700 dark:text-zinc-300">{caseData.brief_facts}</p>
          ) : (
            <p className="text-sm italic text-zinc-400 dark:text-zinc-600">
              {t("caseHeader.briefFactsRestricted")}
            </p>
          )}
        </div>

        {has("edit_case") ? (
          <Button variant="outline" size="sm" className="gap-1.5" onClick={() => setIsEditOpen(true)}>
            <Pencil className="size-3.5" />
            {t("common.edit")}
          </Button>
        ) : null}
      </CardContent>

      <Dialog open={isEditOpen} onOpenChange={setIsEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("caseHeader.editCaseBrief")}</DialogTitle>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor="brief-facts-editor">{t("caseHeader.briefFacts")}</Label>
            <textarea
              id="brief-facts-editor"
              value={draftBriefFacts}
              onChange={(event) => setDraftBriefFacts(event.target.value)}
              rows={6}
              className="w-full rounded-md border border-zinc-300 bg-white p-2.5 text-sm text-zinc-900 outline-none focus-visible:border-accent-400 focus-visible:ring-2 focus-visible:ring-accent-400/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            />
          </div>
          {conflictMessage ? <p className="text-xs text-critical-500">{conflictMessage}</p> : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? t("caseHeader.saving") : t("caseHeader.saveChanges")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  )
}

export { CaseHeaderCard }
