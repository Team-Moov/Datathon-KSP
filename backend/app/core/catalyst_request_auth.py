"""
Per-request Catalyst end-user identity verification — AppSail only.

⚠️ CURRENTLY UNUSED: the backend moved off AppSail to GCP, where the
X-ZC-* headers this relies on are never injected (that's AppSail-platform
plumbing, not something Catalyst attaches anywhere else). /auth/catalyst/exchange
in app/api/v1/endpoints/auth.py now trusts a client-asserted identity instead —
see that endpoint's docstring for the tradeoff. Kept here, working and
documented, for if this backend ever moves back onto AppSail: swap that
endpoint back to calling get_catalyst_identity(request) and the gap closes.

Used exclusively by POST /auth/catalyst/exchange. Every other route keeps
validating our own JWT via get_current_user() in security.py, unchanged.

Why this file exists: Zoho's docs (Implement Catalyst SDK in AppSail —
https://docs.catalyst.zoho.com/en/serverless/help/appsail/implement-catalyst-sdk/)
show zcatalyst_sdk.initialize(req=request) being called per-request, but never
say what makes that trustworthy. Reading the installed zcatalyst-sdk==1.4.0
source (zcatalyst_sdk/_util.py, _constants.py) shows it: initialize() reads
X-ZC-* request headers (X-ZC-User-Cred-Token, X-ZC-Project-Key, etc.) that the
AppSail platform itself injects after validating the caller's Catalyst
session/token at its edge — our code never parses or trusts a raw token
itself. get_current_user() then makes a live call to Catalyst's own API using
that injected credential, so a forged header without a real AppSail-verified
session fails there, not in our code.

Confirmed compatible with FastAPI's Request: parse_headers_from_request()
only does `hasattr(request, "headers")` + `dict(request.headers)`, and
Starlette's Request.headers satisfies that.
"""

from __future__ import annotations

from dataclasses import dataclass

import zcatalyst_sdk
from fastapi import HTTPException, Request, status
from zcatalyst_sdk.exceptions import CatalystError


@dataclass(frozen=True)
class CatalystIdentity:
    email: str
    zuid: str
    role_name: str


def get_catalyst_identity(request: Request) -> CatalystIdentity:
    """
    Raises 401 if the incoming request does not carry a valid, AppSail-verified
    Catalyst end-user session. Never inspects the raw Authorization header
    itself — all trust comes from the platform-injected X-ZC-* headers that
    zcatalyst_sdk.initialize(req=...) reads.
    """
    try:
        catalyst_app = zcatalyst_sdk.initialize(req=request)
        current_user = catalyst_app.authentication().get_current_user()
    except CatalystError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not verify Catalyst identity for this request",
        ) from exc

    email = current_user.get("email_id")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Catalyst identity is missing an email address",
        )

    return CatalystIdentity(
        email=email,
        zuid=str(current_user.get("zuid", "")),
        role_name=(current_user.get("role_details") or {}).get("role_name", ""),
    )
