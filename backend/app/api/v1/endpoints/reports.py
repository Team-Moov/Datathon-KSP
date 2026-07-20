"""
Secure report export/sharing endpoints (§ Enterprise Security & Governance —
Secure Report Sharing).
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.database import get_admin_db, get_db
from app.core.permissions import Permission, require_permission
from app.core.security import verify_password
from app.models.reports import ReportShareLink
from app.models.user import User
from app.services import report_service

router = APIRouter()


class ExportRequest(BaseModel):
    password: Optional[str] = None
    share: bool = False
    expires_in_hours: int = 72
    max_downloads: int = 5


class ShareLinkOut(BaseModel):
    token: str
    expires_at: datetime
    max_downloads: int


@router.post("/cases/{case_id}/export")
async def export_case_report(
    case_id: UUID,
    payload: ExportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EXPORT_REPORT)),
):
    """
    Direct download by default. Pass share=true (requires Permission.SHARE_CASE)
    to instead mint an expiring, download-limited link for handing to someone
    outside the platform.
    """
    try:
        pdf_bytes = await report_service.build_case_report_pdf(db, case_id, issued_to=current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if payload.password:
        pdf_bytes = report_service.apply_password_protection(pdf_bytes, payload.password)

    if payload.share:
        from app.core.permissions import role_has_permission

        if not role_has_permission(current_user.role, Permission.SHARE_CASE):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires Permission.SHARE_CASE")
        link = await report_service.create_share_link(
            db, case_id, current_user, payload.password, payload.expires_in_hours, payload.max_downloads
        )
        await log_audit_event(
            db, action="report.shared", resource_type="case_master", resource_id=str(case_id),
            payload={"expires_at": link.expires_at.isoformat(), "max_downloads": link.max_downloads},
        )
        return ShareLinkOut(token=link.token, expires_at=link.expires_at, max_downloads=link.max_downloads)

    await log_audit_event(db, action="report.exported", resource_type="case_master", resource_id=str(case_id))
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="case-report-{case_id}.pdf"'},
    )


@router.get("/shared/{token}")
async def download_shared_report(
    token: str,
    password: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_admin_db),
):
    """
    Unauthenticated by design — this is the link handed to someone outside the
    platform. Security comes from the token's entropy plus expiry/download-count/
    optional-password enforcement below, not from a bearer token — which is also
    exactly why this can't use the ordinary RLS-bound get_db(): there's no
    logged-in user here for the district-isolation session variables to be set
    from, so the normal session would block the report's own data lookup
    outright rather than merely under-scope it. The token check above is the
    real authorization boundary for this route.
    """
    stmt = select(ReportShareLink).where(ReportShareLink.token == token)
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if link is None or link.revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Link not found")
    if link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Link has expired")
    if link.download_count >= link.max_downloads:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Download limit reached")
    if link.password_hash and not (password and verify_password(password, link.password_hash)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Password required or incorrect")

    creator = await db.get(User, link.created_by)
    try:
        pdf_bytes = await report_service.build_case_report_pdf(db, link.case_id, issued_to=creator)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    if link.password_hash:
        pdf_bytes = report_service.apply_password_protection(pdf_bytes, password)

    link.download_count += 1
    await db.flush()
    await log_audit_event(
        db, action="report.shared_link_downloaded", resource_type="case_master",
        resource_id=str(link.case_id), payload={"download_count": link.download_count},
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="case-report-{link.case_id}.pdf"'},
    )
