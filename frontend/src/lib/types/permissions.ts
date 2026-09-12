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
  | "manage_analytics_jobs"

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
const DGP_TIER: Permission[] = [...SP_TIER, "manage_users", "manage_analytics_jobs"]

const CRIME_ANALYST_TIER: Permission[] = [
  ...DSP_TIER.filter((permission) => permission !== "share_case" && permission !== "manage_case_notes"),
  "manage_analytics_jobs",
]

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

/**
 * Plain-language copy for the public access-scope page. English-only on
 * purpose, matching RANK_LABELS above: these name fixed capability and rank
 * identifiers rather than prose, and the surrounding page chrome is what goes
 * through i18n.
 */
export const RANK_SUMMARIES: Record<PoliceRank, string> = {
  CONSTABLE: "Read-only access to non-sensitive case records and public crime trends.",
  INSPECTOR: "Adds sensitive case detail, unmasked identities, and basic network views.",
  DSP: "Full investigative access, including editing, risk scoring, and financial records.",
  SP: "Everything a DSP can do, plus visibility of the governance audit log.",
  DGP: "Complete access, and the only rank that can administer user accounts.",
  CRIME_ANALYST: "Investigative and analytics access without supervisory sign-off actions.",
  POLICY_MAKER: "Aggregate statistics only, with no access to individual case or person data.",
}

export const PERMISSION_LABELS: Record<Permission, string> = {
  view_case_basic: "View basic case records",
  view_case_sensitive: "View sensitive case detail",
  edit_case: "Create and edit cases",
  manage_case_notes: "Moderate other officers' case notes",
  share_case: "Share a case with another unit",
  generate_case_brief: "Generate AI case briefs",
  verify_person: "Verify person identities",
  view_pii_unmasked: "View unmasked personal data",
  upload_document: "Upload case documents",
  promote_document: "Promote documents to evidence",
  view_network_basic: "View basic criminal networks",
  view_network_advanced: "View advanced network analysis",
  compute_risk_score: "Run recidivism risk scoring",
  review_risk_score: "Review and sign off risk scores",
  view_financial_raw: "View raw financial records",
  view_trends_hotspots: "View crime trends and hotspots",
  view_aggregate_analytics: "View district aggregate analytics",
  export_report: "Export and download reports",
  view_audit_log: "View the governance audit log",
  manage_analytics_jobs: "Trigger analytics and model jobs",
  manage_users: "Manage user accounts and roles",
}

/** Ordering and grouping for the access-scope matrix, coarse to sensitive. */
export const PERMISSION_GROUPS: { title: string; permissions: Permission[] }[] = [
  {
    title: "Cases and records",
    permissions: [
      "view_case_basic",
      "view_case_sensitive",
      "edit_case",
      "generate_case_brief",
      "share_case",
      "manage_case_notes",
    ],
  },
  { title: "People and identity", permissions: ["verify_person", "view_pii_unmasked"] },
  { title: "Documents", permissions: ["upload_document", "promote_document"] },
  { title: "Network analysis", permissions: ["view_network_basic", "view_network_advanced"] },
  {
    title: "Risk and financial",
    permissions: ["compute_risk_score", "review_risk_score", "view_financial_raw"],
  },
  {
    title: "Analytics and reporting",
    permissions: ["view_trends_hotspots", "view_aggregate_analytics", "export_report"],
  },
  {
    title: "Governance",
    permissions: ["view_audit_log", "manage_analytics_jobs", "manage_users"],
  },
]

export const ALL_RANKS: PoliceRank[] = [
  "CONSTABLE",
  "INSPECTOR",
  "DSP",
  "SP",
  "DGP",
  "CRIME_ANALYST",
  "POLICY_MAKER",
]
