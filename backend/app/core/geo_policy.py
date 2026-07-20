"""
Geo-restriction extension point (§ Enterprise Security & Governance — MFA:
geo-location restrictions). No geo-IP data source is available in this
environment, so this is deliberately a permissive no-op rather than a faked
check — wire a real MaxMind/IP2Location lookup into `resolve_country` when one
is available, and login enforcement in auth.py starts working immediately
since it already calls this on every login.
"""

from typing import Optional

from app.core.config import settings


def resolve_country(ip_address: Optional[str]) -> Optional[str]:
    """Placeholder — always returns None (unknown) until a geo-IP source exists."""
    return None


def is_login_permitted(ip_address: Optional[str]) -> bool:
    if not settings.ALLOWED_COUNTRIES:
        return True
    country = resolve_country(ip_address)
    if country is None:
        # Unknown country with a configured allowlist: permissive by default
        # rather than locking users out because geo-IP data isn't wired up yet.
        return True
    return country in settings.ALLOWED_COUNTRIES
