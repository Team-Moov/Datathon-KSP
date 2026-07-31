"""
Early-warning alert endpoints (capability #8).

Gated behind VIEW_NETWORK_ADVANCED — alerts are inherently cross-jurisdiction
findings (multi-jurisdiction offenders, organized groups), the same sensitivity
tier as the community/multi-jurisdiction network endpoints they derive from, so
they reuse that permission rather than inventing a new one. Triggering a scan is
an analytics-job action, gated behind MANAGE_ANALYTICS_JOBS.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.models.alert import Alert
from app.models.enums import AlertStatus, AlertType
from app.models.user import User
from app.services.analytics.early_warning import EarlyWarningService

router = APIRouter()


def _serialize(alert: Alert) -> Dict[str, Any]:
    return {
        "id": str(alert.id),
        "alert_type": alert.alert_type.value,
        "severity": alert.severity.value,
        "status": alert.status.value,
        "title": alert.title,
        "description": alert.description,
        "evidence": alert.evidence,
        "source_tool": alert.source_tool,
        "confidence": alert.confidence,
        "district_id": alert.district_id,
        "subject_person_id": str(alert.subject_person_id) if alert.subject_person_id else None,
        "subject_case_id": str(alert.subject_case_id) if alert.subject_case_id else None,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
        "acknowledged_at": alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
    }


# Severity order for a "most-urgent first" list, newest within each band.
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


@router.get("/", response_model=List[Dict[str, Any]])
async def list_alerts(
    status: Optional[AlertStatus] = Query(None, description="Filter by status; omit for active (new + acknowledged)."),
    alert_type: Optional[AlertType] = Query(None),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_NETWORK_ADVANCED)),
):
    """List early-warning alerts. Default view is active (not dismissed)."""
    stmt = select(Alert)
    if status is not None:
        stmt = stmt.where(Alert.status == status)
    else:
        stmt = stmt.where(Alert.status != AlertStatus.DISMISSED)
    if alert_type is not None:
        stmt = stmt.where(Alert.alert_type == alert_type)
    stmt = stmt.order_by(Alert.created_at.desc()).limit(limit)

    alerts = (await db.execute(stmt)).scalars().all()
    serialized = [_serialize(a) for a in alerts]
    serialized.sort(key=lambda a: (_SEVERITY_RANK.get(a["severity"], 3), a["created_at"] or ""))
    return serialized


@router.get("/summary", response_model=Dict[str, Any])
async def alerts_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_NETWORK_ADVANCED)),
):
    """Counts for the nav badge / dashboard tile: active total + high-severity active."""
    active = (await db.execute(select(Alert).where(Alert.status != AlertStatus.DISMISSED))).scalars().all()
    return {
        "active_total": len(active),
        "high_severity": sum(1 for a in active if a.severity.value == "high"),
        "new": sum(1 for a in active if a.status == AlertStatus.NEW),
    }


async def _set_status(db: AsyncSession, alert_id: UUID, new_status: AlertStatus, user: User) -> Dict[str, Any]:
    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = new_status
    if new_status == AlertStatus.ACKNOWLEDGED:
        alert.acknowledged_by = user.id
        alert.acknowledged_at = datetime.now(timezone.utc)
    await db.flush()
    await log_audit_event(
        db,
        action=f"alert.{new_status.value}",
        resource_type="alert",
        resource_id=str(alert_id),
        payload={"alert_type": alert.alert_type.value, "severity": alert.severity.value},
    )
    return _serialize(alert)


@router.post("/{alert_id}/acknowledge", response_model=Dict[str, Any])
async def acknowledge_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_NETWORK_ADVANCED)),
):
    return await _set_status(db, alert_id, AlertStatus.ACKNOWLEDGED, current_user)


@router.post("/{alert_id}/dismiss", response_model=Dict[str, Any])
async def dismiss_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_NETWORK_ADVANCED)),
):
    return await _set_status(db, alert_id, AlertStatus.DISMISSED, current_user)


@router.post("/scan", response_model=Dict[str, Any])
async def trigger_scan(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_ANALYTICS_JOBS)),
):
    """
    Run the detectors on demand (the same body the Celery beat schedule runs), so
    a demo doesn't have to wait for the hourly tick. Idempotent — re-detecting an
    existing condition inserts nothing.
    """
    result = await EarlyWarningService(db).scan()
    await log_audit_event(db, action="alert.scan", resource_type="alert", payload=result)
    return result
