import { FileWarning, Paperclip } from "lucide-react"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import type { CaseWorkspaceSnapshot } from "@/lib/types/api"

function EvidenceList({ documents }: { documents: CaseWorkspaceSnapshot["documents"] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Evidence &amp; Documents</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        {documents.length === 0 ? (
          <EmptyState icon={FileWarning} title="No documents linked to this case yet" />
        ) : (
          <ul className="divide-y divide-zinc-100 dark:divide-zinc-900">
            {documents.map((doc) => (
              <li key={doc.document_id} className="flex items-start gap-2.5 px-4 py-2.5">
                <Paperclip className="mt-0.5 size-3.5 shrink-0 text-zinc-400" />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm text-zinc-800 dark:text-zinc-100">{doc.original_filename}</p>
                  <p className="text-xs text-zinc-500 dark:text-zinc-400">
                    {doc.source_type} · extracted via {doc.extraction_method} · confidence{" "}
                    {Math.round(doc.confidence_score * 100)}%
                  </p>
                </div>
                {doc.staging_only ? <Badge variant="caution">staged</Badge> : null}
                {!doc.human_verified ? <Badge variant="neutral">unverified</Badge> : null}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export { EvidenceList }
