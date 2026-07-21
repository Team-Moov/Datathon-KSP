/**
 * Mirrors backend/app/core/permissions.py exactly — the capability matrix here
 * must stay in sync with ROLE_PERMISSIONS server-side. This only gates what the
 * UI shows; the API re-checks every one of these server-side regardless, so a
 * drift here is a UX bug (wrong nav item visible/hidden), never a security hole.
 */

export type PoliceRank =
  | "CONSTABLE"
  | "INSPECTOR"
  | "DSP"
  | "SP"
  | "DGP"
  | "CRIME_ANALYST"
  | "POLICY_MAKER"

export type Permission =
  | "view_case_basic"
  | "view_case_sensitive"
  | "edit_case"
  | "verify_person"
  | "view_pii_unmasked"
  | "upload_document"
  | "promote_document"
  | "view_network_basic"
  | "view_network_advanced"
  | "view_trends_hotspots"
  | "compute_risk_score"
  | "review_risk_score"
  | "view_financial_raw"
  | "generate_case_brief"
  | "view_aggregate_analytics"
  | "export_report"
  | "share_case"
  | "view_audit_log"
  | "manage_users"
  | "manage_case_notes"

const CONSTABLE_TIER: Permission[] = ["view_case_basic", "view_trends_hotspots"]

const INSPECTOR_TIER: Permission[] = [
  ...CONSTABLE_TIER,
  "view_case_sensitive",
  "view_pii_unmasked",
  "view_network_basic",
  "generate_case_brief",
]

const DSP_TIER: Permission[] = [
  ...INSPECTOR_TIER,
  "edit_case",
  "verify_person",
  "upload_document",
  "promote_document",
  "view_network_advanced",
  "compute_risk_score",
  "review_risk_score",
  "view_financial_raw",
  "view_aggregate_analytics",
  "export_report",
  "share_case",
  "manage_case_notes",
]

const SP_TIER: Permission[] = [...DSP_TIER, "view_audit_log"]
const DGP_TIER: Permission[] = [...SP_TIER, "manage_users"]

const CRIME_ANALYST_TIER: Permission[] = DSP_TIER.filter(
  (permission) => permission !== "share_case" && permission !== "manage_case_notes",
)

const POLICY_MAKER_TIER: Permission[] = [
  "view_case_basic",
  "view_trends_hotspots",
  "view_aggregate_analytics",
  "view_audit_log",
]

export const ROLE_PERMISSIONS: Record<PoliceRank, Permission[]> = {
  CONSTABLE: CONSTABLE_TIER,
  INSPECTOR: INSPECTOR_TIER,
  DSP: DSP_TIER,
  SP: SP_TIER,
  DGP: DGP_TIER,
  CRIME_ANALYST: CRIME_ANALYST_TIER,
  POLICY_MAKER: POLICY_MAKER_TIER,
}

export function roleHasPermission(role: PoliceRank | undefined, permission: Permission): boolean {
  if (!role) return false
  return ROLE_PERMISSIONS[role]?.includes(permission) ?? false
}

export function roleHasAnyPermission(role: PoliceRank | undefined, permissions: Permission[]): boolean {
  return permissions.some((permission) => roleHasPermission(role, permission))
}

export const RANK_LABELS: Record<PoliceRank, string> = {
  CONSTABLE: "Constable",
  INSPECTOR: "Inspector",
  DSP: "DSP",
  SP: "SP",
  DGP: "DGP",
  CRIME_ANALYST: "Crime Analyst",
  POLICY_MAKER: "Policy Maker",
}
