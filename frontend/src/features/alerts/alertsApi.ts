import { httpClient } from "@/lib/api/httpClient"

export type AlertType = "repeat_offender" | "organized_group" | "emerging_hotspot" | "financial"
export type AlertSeverity = "low" | "medium" | "high"
export type AlertStatus = "new" | "acknowledged" | "dismissed"

export interface EarlyWarningAlert {
  id: string
  alert_type: AlertType
  severity: AlertSeverity
  status: AlertStatus
  title: string
  description: string
  evidence: Record<string, unknown>
  source_tool: string
  confidence: number | null
  district_id: number | null
  subject_person_id: string | null
  subject_case_id: string | null
  created_at: string | null
  acknowledged_at: string | null
}

export interface AlertsSummary {
  active_total: number
  high_severity: number
  new: number
}

export async function fetchAlerts(params?: { status?: AlertStatus; alert_type?: AlertType }) {
  const response = await httpClient.get<EarlyWarningAlert[]>("/alerts/", { params })
  return response.data
}

export async function fetchAlertsSummary() {
  const response = await httpClient.get<AlertsSummary>("/alerts/summary")
  return response.data
}

export async function acknowledgeAlert(alertId: string) {
  const response = await httpClient.post<EarlyWarningAlert>(`/alerts/${alertId}/acknowledge`)
  return response.data
}

export async function dismissAlert(alertId: string) {
  const response = await httpClient.post<EarlyWarningAlert>(`/alerts/${alertId}/dismiss`)
  return response.data
}

/** Requires manage_analytics_jobs — runs the detectors on demand. */
export async function triggerAlertScan() {
  const response = await httpClient.post<{ candidates: number; inserted: number }>("/alerts/scan")
  return response.data
}
