import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import axios from "axios"

import type { CaseWorkspaceSnapshot, WorkspaceNote } from "@/lib/types/api"
import {
  fetchCaseWorkspace,
  removeCaseNote,
  submitCaseNote,
  submitCaseNoteUpdate,
  type NoteUpdatePayload,
} from "./casesApi"

export function workspaceQueryKey(caseId: string) {
  return ["case-workspace", caseId] as const
}

export function isVersionConflict(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 409
}

function buildOptimisticNote(content: string, pinned: boolean): WorkspaceNote {
  return {
    note_id: `optimistic-${crypto.randomUUID()}`,
    author_id: "you",
    content,
    pinned,
    version: 1,
    updated_at: new Date().toISOString(),
  }
}

export function useCaseWorkspace(caseId: string) {
  const queryClient = useQueryClient()
  const queryKey = workspaceQueryKey(caseId)

  const workspaceQuery = useQuery({
    queryKey,
    queryFn: () => fetchCaseWorkspace(caseId),
    enabled: Boolean(caseId),
  })

  // onError doesn't just restore the pre-mutation snapshot — it also
  // invalidates the query so the UI reconciles against real server state
  // rather than trusting a client-side snapshot that may itself be stale.
  function revertAndResync(previous: CaseWorkspaceSnapshot | undefined) {
    if (previous) queryClient.setQueryData(queryKey, previous)
    void queryClient.invalidateQueries({ queryKey })
  }

  const addNoteMutation = useMutation({
    mutationFn: (vars: { content: string; pinned: boolean }) => submitCaseNote(caseId, vars.content, vars.pinned),
    onMutate: async (vars) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<CaseWorkspaceSnapshot>(queryKey)
      if (previous) {
        queryClient.setQueryData<CaseWorkspaceSnapshot>(queryKey, {
          ...previous,
          notes: [buildOptimisticNote(vars.content, vars.pinned), ...previous.notes],
        })
      }
      return { previous }
    },
    onError: (_error, _vars, context) => revertAndResync(context?.previous),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
  })

  const updateNoteMutation = useMutation({
    mutationFn: (vars: { noteId: string; payload: NoteUpdatePayload }) =>
      submitCaseNoteUpdate(caseId, vars.noteId, vars.payload),
    onMutate: async (vars) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<CaseWorkspaceSnapshot>(queryKey)
      if (previous) {
        queryClient.setQueryData<CaseWorkspaceSnapshot>(queryKey, {
          ...previous,
          notes: previous.notes.map((note) =>
            note.note_id === vars.noteId ? { ...note, ...vars.payload } : note,
          ),
        })
      }
      return { previous }
    },
    onError: (_error, _vars, context) => revertAndResync(context?.previous),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
  })

  const deleteNoteMutation = useMutation({
    mutationFn: (noteId: string) => removeCaseNote(caseId, noteId),
    onMutate: async (noteId) => {
      await queryClient.cancelQueries({ queryKey })
      const previous = queryClient.getQueryData<CaseWorkspaceSnapshot>(queryKey)
      if (previous) {
        queryClient.setQueryData<CaseWorkspaceSnapshot>(queryKey, {
          ...previous,
          notes: previous.notes.filter((note) => note.note_id !== noteId),
        })
      }
      return { previous }
    },
    onError: (_error, _vars, context) => revertAndResync(context?.previous),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey }),
  })

  return {
    workspaceSnapshot: workspaceQuery.data,
    isLoading: workspaceQuery.isLoading,
    isError: workspaceQuery.isError,
    error: workspaceQuery.error,
    refetch: workspaceQuery.refetch,
    addNoteMutation,
    updateNoteMutation,
    deleteNoteMutation,
  }
}
