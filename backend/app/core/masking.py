"""
Named, per-field masking (§ Enterprise Security & Governance — Data Masking).

Every function targets one specific real column, matching the design doc's own
rule (§11): "named, specific access-control flags... never a generic 'watch for
sensitive fields' gesture." There is no mask_any_field() utility here on purpose.
"""

from typing import Optional


def mask_person_display_name(
    full_name: str,
    has_permission: bool,
    role_label: Optional[str] = None,
    ordinal: Optional[str] = None,
) -> str:
    """
    Person.full_name (design doc §3.1). Outside a case-role context — plain
    /persons lookups, where a Person may hold different roles across different
    cases — falls back to a generic redaction. Inside a single case's workspace,
    callers pass the real role_label/ordinal for a "Victim A" style label
    (see app/services/workspace_service.py).
    """
    if has_permission:
        return full_name
    if role_label and ordinal:
        return f"{role_label} {ordinal}"
    return "Redacted"


def mask_address(address: Optional[str], has_permission: bool) -> Optional[str]:
    """Person.permanent_address / Person.present_address (§3.1)."""
    if has_permission or address is None:
        return address
    return None


def mask_religion_caste(value: Optional[int], has_permission: bool) -> Optional[int]:
    """
    PersonCaseRole.religion_id / PersonCaseRole.caste_id — the exact columns the
    design doc names explicitly (§3.3, §7.3): "any read of these columns MUST go
    through an access-control check."
    """
    if has_permission:
        return value
    return None


def mask_account_number(account: str) -> str:
    """FinancialTransaction.from_account / to_account (§3.1, §9)."""
    if not account:
        return account
    if len(account) <= 4:
        return "XXXX"
    return f"XXXX XXXX {account[-4:]}"
