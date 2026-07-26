import { httpClient } from "@/lib/api/httpClient"
import type { CaseStageEventOut, CaseSummary, CaseWorkspaceSnapshot, WorkspaceNote } from "@/lib/types/api"

export interface CaseListFilters {
  districtId?: number
  crimeHeadId?: number
  startDate?: string
  endDate?: string
  skip?: number
  limit?: number
}

export async function fetchCaseList(filters: CaseListFilters = {}): Promise<CaseSummary[]> {
  const response = await httpClient.get<CaseSummary[]>("/cases/", {
    params: {
      district_id: filters.districtId,
      crime_head_id: filters.crimeHeadId,
      start_date: filters.startDate,
      end_date: filters.endDate,
      skip: filters.skip ?? 0,
      limit: filters.limit ?? 50,
    },
  })
  return response.data
}

export async function fetchCaseByCrimeNo(crimeNo: string): Promise<CaseSummary> {
  const response = await httpClient.get<CaseSummary>(`/cases/${crimeNo}`)
  return response.data
}

export async function fetchCaseStageEvents(caseId: string): Promise<CaseStageEventOut[]> {
  const response = await httpClient.get<CaseStageEventOut[]>(`/cases/${caseId}/stages`)
  return response.data
}

export async function generateCaseBrief(caseId: string): Promise<Record<string, unknown>> {
  const response = await httpClient.get(`/cases/${caseId}/brief`)
  return response.data
}

export interface CaseUpdatePayload {
  version: number
  brief_facts?: string
  case_status_id?: number
  reason?: string
}

export async function submitCaseUpdate(caseId: string, payload: CaseUpdatePayload): Promise<CaseSummary> {
  const response = await httpClient.patch<CaseSummary>(`/cases/${caseId}`, payload)
  return response.data
}

export async function fetchCaseWorkspace(caseId: string): Promise<CaseWorkspaceSnapshot> {
  const response = await httpClient.get<CaseWorkspaceSnapshot>(`/workspace/cases/${caseId}`)
  return response.data
}

export async function submitCaseNote(caseId: string, content: string, pinned: boolean): Promise<WorkspaceNote> {
  const response = await httpClient.post<WorkspaceNote>(`/workspace/cases/${caseId}/notes`, { content, pinned })
  return response.data
}

export interface NoteUpdatePayload {
  version: number
  content?: string
  pinned?: boolean
}

export async function submitCaseNoteUpdate(
  caseId: string,
  noteId: string,
  payload: NoteUpdatePayload,
): Promise<WorkspaceNote> {
  const response = await httpClient.patch<WorkspaceNote>(`/workspace/cases/${caseId}/notes/${noteId}`, payload)
  return response.data
}

export async function removeCaseNote(caseId: string, noteId: string): Promise<void> {
  await httpClient.delete(`/workspace/cases/${caseId}/notes/${noteId}`)
}

export interface ReportExportOptions {
  password?: string
  share?: boolean
  expiresInHours?: number
  maxDownloads?: number
}

export async function initiateReportExport(caseId: string, options: ReportExportOptions = {}) {
  if (options.share) {
    const response = await httpClient.post(`/reports/cases/${caseId}/export`, {
      password: options.password,
      share: true,
      expires_in_hours: options.expiresInHours ?? 72,
      max_downloads: options.maxDownloads ?? 5,
    })
    return response.data as { token: string; expires_at: string; max_downloads: number }
  }

  const response = await httpClient.post(
    `/reports/cases/${caseId}/export`,
    { password: options.password, share: false },
    { responseType: "blob" },
  )
  return response.data as Blob
}

// ── Dashboard stats ───────────────────────────────────────────────────────────

export interface CaseStats {
  total_cases: number
  recent_cases_7d: number
  suspect_count: number
  crime_distribution: { name: string; value: number }[]
}

/**
 * Lightweight aggregate counts used by the Overview dashboard.
 * Backed by the deterministic /cases/stats endpoint — no hardcoded numbers.
 */
export async function fetchCaseStats(): Promise<CaseStats> {
  const response = await httpClient.get<CaseStats>("/cases/stats")
  return response.data
}
