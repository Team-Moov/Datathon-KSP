"""
Per-request context — lets audit logging and change tracking read who/where/how
without threading user_id/ip/user_agent through every service function signature.

Populated in two stages: RequestContextMiddleware captures ip/user_agent as soon as
the request arrives (before auth is even resolved), and get_current_user (security.py)
fills in current_user_id once the token is validated.
"""

from contextvars import ContextVar
from typing import Optional
from uuid import UUID

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

current_user_id_ctx: ContextVar[Optional[UUID]] = ContextVar("current_user_id", default=None)
client_ip_ctx: ContextVar[Optional[str]] = ContextVar("client_ip", default=None)
user_agent_ctx: ContextVar[Optional[str]] = ContextVar("user_agent", default=None)

# Set by an edit endpoint just before the flush that triggers change_tracking's
# before_flush listener — this is the "Why" in the immutable change history's
# Old Value / New Value / Who / When / Why. Endpoints that don't set it (most
# writes have no user-supplied reason) leave RecordChangeHistory.reason NULL.
change_reason_ctx: ContextVar[Optional[str]] = ContextVar("change_reason", default=None)


def _resolve_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip_token = client_ip_ctx.set(_resolve_client_ip(request))
        ua_token = user_agent_ctx.set(request.headers.get("user-agent"))
        try:
            return await call_next(request)
        finally:
            client_ip_ctx.reset(ip_token)
            user_agent_ctx.reset(ua_token)
