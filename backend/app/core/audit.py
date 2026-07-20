"""
Audit-event logging (§ Enterprise Security & Governance — Audit Trail & Activity Logs).
Call sites stay lean because who/where/how is read from request_context rather than
threaded through every function signature — see app/core/request_context.py.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.request_context import client_ip_ctx, current_user_id_ctx, user_agent_ctx
from app.models.audit import AuditLog


async def log_audit_event(
    db: AsyncSession,
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
    reason: Optional[str] = None,
    user_id: Optional[UUID] = None,
) -> AuditLog:
    """
    Record one audit entry. `user_id` is only needed to override the context value —
    e.g. logging a login attempt where get_current_user hasn't resolved the caller
    onto current_user_id_ctx yet.
    """
    entry = AuditLog(
        user_id=user_id or current_user_id_ctx.get(),
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        payload=payload,
        ip_address=client_ip_ctx.get(),
        user_agent=user_agent_ctx.get(),
        reason=reason,
    )
    db.add(entry)
    await db.flush()
    return entry
