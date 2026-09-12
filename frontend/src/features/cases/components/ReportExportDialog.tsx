import * as React from "react"
import { useMutation } from "@tanstack/react-query"
import { Download, Share2 } from "lucide-react"
import { toast } from "sonner"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { API_ORIGIN, extractApiErrorMessage } from "@/lib/api/httpClient"
import { usePermission } from "@/lib/hooks/usePermission"
import { initiateReportExport } from "../casesApi"

function triggerBrowserDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function ReportExportDialog({ caseId, crimeNo }: { caseId: string; crimeNo: string }) {
  const { t } = useTranslation()
  const { has } = usePermission()
  const [isOpen, setIsOpen] = React.useState(false)
  const [password, setPassword] = React.useState("")
  const [shareLink, setShareLink] = React.useState(false)
  const [shareResult, setShareResult] = React.useState<{ token: string; expiresAt: string } | null>(null)

  const exportMutation = useMutation({
    mutationFn: () => initiateReportExport(caseId, { password: password || undefined, share: shareLink }),
    onSuccess: (result) => {
      if (shareLink) {
        const shareData = result as { token: string; expires_at: string; max_downloads: number }
        setShareResult({ token: shareData.token, expiresAt: shareData.expires_at })
        toast.success(t("reportExport.shareLinkCreatedToast"))
        return
      }
      triggerBrowserDownload(result as Blob, `case-report-${crimeNo}.pdf`)
      setIsOpen(false)
      toast.success(t("reportExport.reportDownloadedToast"))
    },
    onError: (error) => toast.error(extractApiErrorMessage(error, t("reportExport.couldntGenerateReport"))),
  })

  if (!has("export_report")) return null

  // API_ORIGIN, not the page origin: this link is handed to someone to open
  // directly, and the report is served by the backend, not by the static host
  // this app is served from.
  const shareUrl = shareResult ? `${API_ORIGIN}/api/v1/reports/shared/${shareResult.token}` : null

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        setIsOpen(open)
        if (!open) setShareResult(null)
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Download className="size-3.5" />
          {t("reportExport.exportReport")}
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t("reportExport.exportCaseReport")}</DialogTitle>
          <DialogDescription>
            {t("reportExport.exportDesc")}
          </DialogDescription>
        </DialogHeader>

        {shareResult && shareUrl ? (
          <div className="space-y-2">
            <Label>{t("reportExport.shareLinkExpires", { date: new Date(shareResult.expiresAt).toLocaleString() })}</Label>
            <div className="flex gap-2">
              <Input readOnly value={shareUrl} className="font-mono text-xs" />
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  void navigator.clipboard.writeText(shareUrl)
                  toast.success(t("reportExport.copiedToClipboard"))
                }}
              >
                {t("reportExport.copy")}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="report-password">{t("reportExport.passwordProtect")}</Label>
              <Input
                id="report-password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={t("reportExport.passwordPlaceholder")}
              />
            </div>

            {has("share_case") ? (
              <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-200">
                <Checkbox checked={shareLink} onCheckedChange={(checked) => setShareLink(checked === true)} />
                {t("reportExport.createShareLinkInstead")}
              </label>
            ) : null}
          </div>
        )}

        <DialogFooter>
          {!shareResult ? (
            <Button onClick={() => exportMutation.mutate()} disabled={exportMutation.isPending} className="gap-1.5">
              {shareLink ? <Share2 className="size-3.5" /> : <Download className="size-3.5" />}
              {exportMutation.isPending ? t("reportExport.working") : shareLink ? t("reportExport.createShareLinkBtn") : t("reportExport.downloadPdf")}
            </Button>
          ) : null}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export { ReportExportDialog }
