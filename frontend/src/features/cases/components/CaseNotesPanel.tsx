import * as React from "react"
import { Pin, PinOff, StickyNote, Trash2 } from "lucide-react"
import { useTranslation } from "react-i18next"
import type { TFunction } from "i18next"

import { EmptyState } from "@/components/data-states/EmptyState"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { extractApiErrorMessage } from "@/lib/api/httpClient"
import { usePermission } from "@/lib/hooks/usePermission"
import type { WorkspaceNote } from "@/lib/types/api"
import { isVersionConflict, useCaseWorkspace } from "../useCaseWorkspace"

interface CaseNotesPanelProps {
  caseId: string
  notes: WorkspaceNote[]
  currentUserId: string | undefined
}

function NoteItem({
  note,
  canManage,
  onTogglePin,
  onDelete,
  t,
}: {
  note: WorkspaceNote
  canManage: boolean
  onTogglePin: () => void
  onDelete: () => void
  t: TFunction
}) {
  return (
    <li className="flat-surface rounded-md p-3">
      <div className="flex items-start justify-between gap-2">
        <p className="whitespace-pre-wrap text-sm text-zinc-700 dark:text-zinc-200">{note.content}</p>
        {canManage ? (
          <div className="flex shrink-0 gap-1">
            <button
              type="button"
              onClick={onTogglePin}
              className="rounded p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
              title={note.pinned ? t("caseNotes.unpin") : t("caseNotes.pin")}
            >
              {note.pinned ? <PinOff className="size-3.5" /> : <Pin className="size-3.5" />}
            </button>
            <button
              type="button"
              onClick={onDelete}
              className="rounded p-1 text-zinc-400 hover:bg-critical-500/10 hover:text-critical-600"
              title={t("caseNotes.deleteNote")}
            >
              <Trash2 className="size-3.5" />
            </button>
          </div>
        ) : null}
      </div>
      <p className="mt-1.5 text-[11px] text-zinc-400 dark:text-zinc-500">
        {note.pinned ? `${t("caseNotes.pinned")} · ` : ""}
        {new Date(note.updated_at).toLocaleString()}
      </p>
    </li>
  )
}

function CaseNotesPanel({ caseId, notes, currentUserId }: CaseNotesPanelProps) {
  const { t } = useTranslation()
  const { has } = usePermission()
  const { addNoteMutation, updateNoteMutation, deleteNoteMutation } = useCaseWorkspace(caseId)
  const [draftContent, setDraftContent] = React.useState("")
  const [conflictMessage, setConflictMessage] = React.useState<string | null>(null)

  const canAddNotes = has("view_case_sensitive")
  const canManageAnyNote = has("manage_case_notes")

  function handleAddNote(event: React.FormEvent) {
    event.preventDefault()
    if (!draftContent.trim()) return
    addNoteMutation.mutate(
      { content: draftContent.trim(), pinned: false },
      { onSuccess: () => setDraftContent("") },
    )
  }

  function handleTogglePin(note: WorkspaceNote) {
    setConflictMessage(null)
    updateNoteMutation.mutate(
      { noteId: note.note_id, payload: { version: note.version, pinned: !note.pinned } },
      {
        onError: (error) => {
          setConflictMessage(
            isVersionConflict(error)
              ? t("caseNotes.noteChangedElsewhere")
              : extractApiErrorMessage(error),
          )
        },
      },
    )
  }

  function handleDelete(note: WorkspaceNote) {
    deleteNoteMutation.mutate(note.note_id, {
      onError: (error) => setConflictMessage(extractApiErrorMessage(error)),
    })
  }

  const sortedNotes = [...notes].sort((a, b) => Number(b.pinned) - Number(a.pinned))

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("caseNotes.investigatorNotes")}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {canAddNotes ? (
          <form onSubmit={handleAddNote} className="space-y-2">
            <textarea
              value={draftContent}
              onChange={(event) => setDraftContent(event.target.value)}
              placeholder={t("caseNotes.addObservationPlaceholder")}
              rows={3}
              className="w-full rounded-md border border-zinc-300 bg-white p-2.5 text-sm text-zinc-900 outline-none focus-visible:border-accent-400 focus-visible:ring-2 focus-visible:ring-accent-400/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            />
            <div className="flex justify-end">
              <Button type="submit" size="sm" disabled={addNoteMutation.isPending || !draftContent.trim()}>
                {addNoteMutation.isPending ? t("caseNotes.adding") : t("caseNotes.addNote")}
              </Button>
            </div>
          </form>
        ) : null}

        {conflictMessage ? <p className="text-xs text-critical-500">{conflictMessage}</p> : null}

        {sortedNotes.length === 0 ? (
          <EmptyState icon={StickyNote} title={t("caseNotes.noNotesYet")} description={t("caseNotes.noNotesYetDesc")} />
        ) : (
          <ul className="space-y-2">
            {sortedNotes.map((note) => (
              <NoteItem
                key={note.note_id}
                note={note}
                canManage={canManageAnyNote || note.author_id === currentUserId}
                onTogglePin={() => handleTogglePin(note)}
                onDelete={() => handleDelete(note)}
                t={t}
              />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}

export { CaseNotesPanel }
