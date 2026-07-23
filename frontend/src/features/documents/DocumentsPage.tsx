import * as React from "react"
import { useMutation } from "@tanstack/react-query"
import { FileText, Loader2, ScanText, Tags, UploadCloud } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { extractEntities, ocrDocument, promoteDocument, uploadDocument } from "./documentsApi"

const EntitiesList = React.lazy(() => import("@/components/charts/EntitiesList").then((m) => ({ default: m.EntitiesList })))

function UploadSection() {
  const [file, setFile] = React.useState<File | null>(null)
  const mutation = useMutation({ mutationFn: () => uploadDocument(file!) })
  const promoteMutation = useMutation({ mutationFn: (documentId: string) => promoteDocument(documentId) })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload &amp; ingest</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Runs the full ingestion pipeline for any supported format (FIR PDF, chargesheet, history-sheet, statement
          audio, news HTML, CSV/XLSX). News lands in staging and needs explicit promotion (§2.2 — never auto-merged).
        </p>
        <div className="flex items-end gap-3">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="doc-upload">File</Label>
            <Input id="doc-upload" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </div>
          <Button onClick={() => mutation.mutate()} disabled={!file || mutation.isPending} className="gap-1.5">
            {mutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <UploadCloud className="size-4" />}
            Upload
          </Button>
        </div>
        {mutation.isError ? <p className="text-xs text-critical-500">{extractApiErrorMessage(mutation.error)}</p> : null}
        {mutation.data ? (
          <div className="flat-surface space-y-2 rounded-md p-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-mono text-zinc-700 dark:text-zinc-300">{mutation.data.original_filename}</span>
              {mutation.data.staging_only ? <Badge variant="caution">Staged — needs promotion</Badge> : <Badge variant="affirm">Ingested</Badge>}
            </div>
            <p className="text-zinc-500">
              {mutation.data.source_type} · {mutation.data.file_format} · confidence {Math.round(mutation.data.confidence_score * 100)}%
            </p>
            {mutation.data.staging_only ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => promoteMutation.mutate(mutation.data!.id)}
                disabled={promoteMutation.isPending || promoteMutation.isSuccess}
              >
                {promoteMutation.isSuccess ? "Promoted" : promoteMutation.isPending ? "Promoting..." : "Promote to verified"}
              </Button>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function OcrSection({ onTextExtracted }: { onTextExtracted: (text: string) => void }) {
  const [file, setFile] = React.useState<File | null>(null)
  const [language, setLanguage] = React.useState("")
  const mutation = useMutation({ mutationFn: () => ocrDocument(file!, language.trim() || undefined) })

  return (
    <Card>
      <CardHeader>
        <CardTitle>OCR a file</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-xs text-zinc-500 dark:text-zinc-400">
          Local mode only reads digital-text PDFs; scanned images/handwriting need Zia OCR (OCR_PROVIDER=zia).
        </p>
        <div className="flex items-end gap-3">
          <div className="flex-1 space-y-1.5">
            <Label htmlFor="ocr-upload">File</Label>
            <Input id="ocr-upload" type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </div>
          <div className="w-28 space-y-1.5">
            <Label htmlFor="ocr-language">Language</Label>
            <Input id="ocr-language" value={language} onChange={(event) => setLanguage(event.target.value)} placeholder="kn" />
          </div>
          <Button onClick={() => mutation.mutate()} disabled={!file || mutation.isPending} className="gap-1.5">
            {mutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <ScanText className="size-4" />}
            Run OCR
          </Button>
        </div>
        {mutation.isError ? <p className="text-xs text-critical-500">{extractApiErrorMessage(mutation.error)}</p> : null}
        {mutation.data ? (
          <div className="flat-surface space-y-2 rounded-md p-3 text-xs">
            <div className="flex items-center justify-between text-[10px] text-zinc-400">
              <span>{mutation.data.provider} · confidence {Math.round(mutation.data.confidence * 100)}%</span>
              {mutation.data.text ? (
                <Button size="sm" variant="ghost" className="h-6 px-2" onClick={() => onTextExtracted(mutation.data!.text)}>
                  Send to entity extraction ↓
                </Button>
              ) : null}
            </div>
            {mutation.data.note ? <p className="italic text-caution-600 dark:text-caution-400">{mutation.data.note}</p> : null}
            {mutation.data.text ? (
              <p className="max-h-40 overflow-y-auto whitespace-pre-wrap text-zinc-700 dark:text-zinc-300">{mutation.data.text}</p>
            ) : (
              <EmptyState icon={FileText} title="No text extracted" />
            )}
          </div>
        ) : null}
      </CardContent>
    </Card>
  )
}

function NerSection({ text, onTextChange }: { text: string; onTextChange: (text: string) => void }) {
  const mutation = useMutation({ mutationFn: () => extractEntities(text) })

  return (
    <Card>
      <CardHeader>
        <CardTitle>Extract entities</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <textarea
          value={text}
          onChange={(event) => onTextChange(event.target.value)}
          placeholder="Paste narrative text, or send OCR output here..."
          rows={5}
          className="w-full rounded-md border border-zinc-300 bg-white p-2.5 text-sm text-zinc-900 outline-none focus-visible:border-accent-400 focus-visible:ring-2 focus-visible:ring-accent-400/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
        />
        <Button onClick={() => mutation.mutate()} disabled={!text.trim() || mutation.isPending} className="gap-1.5">
          {mutation.isPending ? <Loader2 className="size-4 animate-spin" /> : <Tags className="size-4" />}
          Extract entities
        </Button>
        {mutation.isError ? <p className="text-xs text-critical-500">{extractApiErrorMessage(mutation.error)}</p> : null}
        {mutation.data ? (
          <React.Suspense fallback={null}>
            <EntitiesList entities={mutation.data.entities} />
          </React.Suspense>
        ) : null}
      </CardContent>
    </Card>
  )
}

/** Frontend surface for the Catalyst-backed document tools (Zia OCR/NER,
 * ingestion pipeline) — the endpoints existed but had never had a page. */
function DocumentsPage() {
  const [nerText, setNerText] = React.useState("")

  return (
    <div className="space-y-4">
      <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">Documents</h1>
      <p className="max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
        Upload evidence for full ingestion, run OCR on a scanned/digital file, or extract named entities from text —
        provider is configurable (OCR_PROVIDER/NLP_PROVIDER: local, zia, or gemini for NER).
      </p>

      <UploadSection />
      <OcrSection onTextExtracted={setNerText} />
      <NerSection text={nerText} onTextChange={setNerText} />
    </div>
  )
}

export { DocumentsPage }
