"""
Capability-based RBAC (§10 of the design doc, "Secure Role-Based Access & Governance").

The seven ranks in app.models.enums.Role don't form one clean chain — CRIME_ANALYST
and POLICY_MAKER are specialist tracks, not command rungs — so access is expressed as
named capabilities per role rather than a single numeric hierarchy check. Every grant
below traces back to a concrete existing endpoint (see the historical require_roles(...)
call sites this replaces), plus the handful of new capabilities the governance features
in this pass introduce (edit_case, export_report, view_audit_log, manage_users, ...).
"""

import enum
from typing import FrozenSet

from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user
from app.models.enums import Role
from app.models.user import User


class Permission(str, enum.Enum):
    VIEW_CASE_BASIC = "view_case_basic"
    VIEW_CASE_SENSITIVE = "view_case_sensitive"          # brief_facts, unmasked identity fields
    EDIT_CASE = "edit_case"
    VERIFY_PERSON = "verify_person"
    VIEW_PII_UNMASKED = "view_pii_unmasked"
    UPLOAD_DOCUMENT = "upload_document"
    PROMOTE_DOCUMENT = "promote_document"
    VIEW_NETWORK_BASIC = "view_network_basic"            # ego network, co-offending, predicted links
    VIEW_NETWORK_ADVANCED = "view_network_advanced"      # community detection, multi-jurisdiction
    VIEW_TRENDS_HOTSPOTS = "view_trends_hotspots"
    COMPUTE_RISK_SCORE = "compute_risk_score"
    REVIEW_RISK_SCORE = "review_risk_score"
    VIEW_FINANCIAL_RAW = "view_financial_raw"
    GENERATE_CASE_BRIEF = "generate_case_brief"
    VIEW_AGGREGATE_ANALYTICS = "view_aggregate_analytics"  # district-year socio/crime-stat aggregates only
    EXPORT_REPORT = "export_report"
    SHARE_CASE = "share_case"
    VIEW_AUDIT_LOG = "view_audit_log"
    MANAGE_USERS = "manage_users"
    MANAGE_CASE_NOTES = "manage_case_notes"              # delete/moderate notes authored by someone else
    MANAGE_ANALYTICS_JOBS = "manage_analytics_jobs"      # trigger GWR recompute / embedding backfill batch jobs


_CONSTABLE_TIER: FrozenSet[Permission] = frozenset(
    {Permission.VIEW_CASE_BASIC, Permission.VIEW_TRENDS_HOTSPOTS}
)

_INSPECTOR_TIER: FrozenSet[Permission] = _CONSTABLE_TIER | {
    Permission.VIEW_CASE_SENSITIVE,
    Permission.VIEW_PII_UNMASKED,
    Permission.VIEW_NETWORK_BASIC,
    Permission.GENERATE_CASE_BRIEF,
}

_DSP_TIER: FrozenSet[Permission] = _INSPECTOR_TIER | {
    Permission.EDIT_CASE,
    Permission.VERIFY_PERSON,
    Permission.UPLOAD_DOCUMENT,
    Permission.PROMOTE_DOCUMENT,
    Permission.VIEW_NETWORK_ADVANCED,
    Permission.COMPUTE_RISK_SCORE,
    Permission.REVIEW_RISK_SCORE,
    Permission.VIEW_FINANCIAL_RAW,
    Permission.VIEW_AGGREGATE_ANALYTICS,
    Permission.EXPORT_REPORT,
    Permission.SHARE_CASE,
    Permission.MANAGE_CASE_NOTES,
}

_SP_TIER: FrozenSet[Permission] = _DSP_TIER | {Permission.VIEW_AUDIT_LOG}

_DGP_TIER: FrozenSet[Permission] = _SP_TIER | {Permission.MANAGE_USERS, Permission.MANAGE_ANALYTICS_JOBS}

# CRIME_ANALYST mirrors the data-steward capabilities of DSP-tier (they did this work
# under the old ANALYST role) without the command-only actions (SHARE_CASE — a
# supervisory sign-off — and MANAGE_CASE_NOTES moderation).
_CRIME_ANALYST_TIER: FrozenSet[Permission] = (
    _DSP_TIER - {Permission.SHARE_CASE, Permission.MANAGE_CASE_NOTES}
) | {Permission.MANAGE_ANALYTICS_JOBS}

# POLICY_MAKER is deliberately aggregate-only — no case PII, no network graph, no
# case editing. This is the design doc §6.1 ecological-fallacy/individual-data wall,
# expressed as a permission grant rather than a data-layer check.
_POLICY_MAKER_TIER: FrozenSet[Permission] = frozenset(
    {
        Permission.VIEW_CASE_BASIC,
        Permission.VIEW_TRENDS_HOTSPOTS,
        Permission.VIEW_AGGREGATE_ANALYTICS,
        Permission.VIEW_AUDIT_LOG,
    }
)

ROLE_PERMISSIONS: dict[Role, FrozenSet[Permission]] = {
    Role.CONSTABLE: _CONSTABLE_TIER,
    Role.INSPECTOR: _INSPECTOR_TIER,
    Role.DSP: _DSP_TIER,
    Role.SP: _SP_TIER,
    Role.DGP: _DGP_TIER,
    Role.CRIME_ANALYST: _CRIME_ANALYST_TIER,
    Role.POLICY_MAKER: _POLICY_MAKER_TIER,
}


def role_has_permission(role: Role, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, frozenset())


def require_permission(*permissions: Permission):
    """
    FastAPI dependency factory — grants access if the caller's role holds ANY of the
    listed permissions (mirrors the historical require_roles(*roles) semantics).
    """

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        granted = ROLE_PERMISSIONS.get(current_user.role, frozenset())
        if not granted.intersection(permissions):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of permissions: {[p.value for p in permissions]}",
            )
        return current_user

    return _check
