/**
 * TS shapes mirroring the backend's Pydantic response models. Kept hand-written
 * rather than codegen'd — the surface area changes slowly enough that a
 * generator would be more ceremony than the types themselves.
 */

import type { PoliceRank } from "./permissions"

export interface AuthenticatedUser {
  id: string
  email: string
  full_name: string
  role: PoliceRank
  is_active: boolean
  badge_number: string | null
  district_id: number | null
  unit_id: number | null
  needs_role_selection: boolean
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: "bearer"
}

export interface CaseSummary {
  id: string
  crime_no: string
  date_reported: string | null
  district_id: number | null
  crime_head_id: number | null
  case_status_id: number | null
  source_type: string
  brief_facts: string | null
  version: number
  // Not currently returned by the case-listing endpoint — optional so
  // OverviewPage.tsx's `|| "Unknown District"` fallback both type-checks and
  // matches actual runtime behavior (always undefined today).
  district_name?: string
  crime_group?: string
}

export interface CaseStageEventOut {
  stage: string
  event_date: string
  confidence: number
  source_document_id: string | null
}

export interface WorkspacePerson {
  person_id: string
  name: string
  human_verified: boolean
  arrested: boolean
  bail_granted: boolean | null
  religion_id: number | null
  caste_id: number | null
}

export interface WorkspaceDocument {
  document_id: string
  original_filename: string
  source_type: string
  extraction_method: string
  confidence_score: number
  human_verified: boolean
  staging_only: boolean
}

export interface WorkspaceNote {
  note_id: string
  author_id: string
  content: string
  pinned: boolean
  version: number
  updated_at: string
}

export interface CaseWorkspaceSnapshot {
  case: {
    id: string
    crime_no: string
    date_reported: string | null
    district_id: number | null
    case_status_id: number | null
    brief_facts: string | null
    disposition: string | null
    version: number
  }
  people: Record<string, WorkspacePerson[]>
  documents: WorkspaceDocument[]
  timeline: { stage: string; event_date: string; confidence: number }[]
  notes: WorkspaceNote[]
}

export interface PersonSummary {
  id: string
  full_name: string
  aliases: string[] | null
  nationality: string | null
  permanent_address: string | null
  present_address: string | null
  human_verified: boolean
  version: number
}

export interface AuditLogEntry {
  id: string
  user_id: string | null
  action: string
  resource_type: string
  resource_id: string | null
  ip_address: string | null
  user_agent: string | null
  reason: string | null
  created_at: string
}

export interface ApiErrorPayload {
  detail?: string
  error?: string
  message?: string
}

export interface ChatSuggestion {
  label: string
  query: string
}

export interface ChatStreamEvent {
  type: "token" | "tool_call" | "tool_result" | "widget" | "error" | "done" | "suggestions"
  content?: string
  tool?: string
  status?: string
  data?: unknown
  widget_type?: string
  error?: string
  message?: string
  items?: ChatSuggestion[]
}
