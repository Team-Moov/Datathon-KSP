import { httpClient } from "@/lib/api/httpClient"
import type { AuditLogEntry } from "@/lib/types/api"
import type { PoliceRank } from "@/lib/types/permissions"

export interface AdminUserRecord {
  id: string
  email: string
  full_name: string
  role: PoliceRank
  is_active: boolean
  badge_number: string | null
  district_id: number | null
  unit_id: number | null
}

export interface AuditLogFilters {
  action?: string
  resourceType?: string
  resourceId?: string
  skip?: number
  limit?: number
}

export async function fetchAuditLog(filters: AuditLogFilters = {}): Promise<AuditLogEntry[]> {
  const response = await httpClient.get<AuditLogEntry[]>("/admin/audit-log", {
    params: {
      action: filters.action || undefined,
      resource_type: filters.resourceType || undefined,
      resource_id: filters.resourceId || undefined,
      skip: filters.skip ?? 0,
      limit: filters.limit ?? 100,
    },
  })
  return response.data
}

export async function fetchAdminUserList(): Promise<AdminUserRecord[]> {
  const response = await httpClient.get<AdminUserRecord[]>("/admin/users")
  return response.data
}

export interface CreateUserPayload {
  email: string
  password: string
  full_name: string
  role: PoliceRank
  badge_number?: string
  district_id?: number
  unit_id?: number
}

export async function submitNewUser(payload: CreateUserPayload): Promise<AdminUserRecord> {
  const response = await httpClient.post<AdminUserRecord>("/admin/users", payload)
  return response.data
}

export async function submitUserRoleChange(userId: string, role: PoliceRank): Promise<AdminUserRecord> {
  const response = await httpClient.patch<AdminUserRecord>(`/admin/users/${userId}/role`, { role })
  return response.data
}

export async function submitUserDeactivation(userId: string): Promise<AdminUserRecord> {
  const response = await httpClient.post<AdminUserRecord>(`/admin/users/${userId}/deactivate`)
  return response.data
}

export interface JobTrigger {
  task_id: string
  task_name: string
}

export type JobStatus = "PENDING" | "STARTED" | "RETRY" | "SUCCESS" | "FAILURE"

export interface JobStatusRecord {
  task_id: string
  status: JobStatus
  result: Record<string, unknown> | null
  error: string | null
}

export async function triggerGwrRecompute(): Promise<JobTrigger> {
  const response = await httpClient.post<JobTrigger>("/admin/jobs/recompute-gwr")
  return response.data
}

export async function triggerEmbeddingBackfill(): Promise<JobTrigger> {
  const response = await httpClient.post<JobTrigger>("/admin/jobs/backfill-embeddings")
  return response.data
}

export async function fetchJobStatus(taskId: string): Promise<JobStatusRecord> {
  const response = await httpClient.get<JobStatusRecord>(`/admin/jobs/${taskId}`)
  return response.data
}
