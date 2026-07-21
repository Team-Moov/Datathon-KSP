"""Cases CRUD and stage-event endpoints."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.database import get_db
from app.core.permissions import Permission, require_permission, role_has_permission
from app.core.request_context import change_reason_ctx
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.case_repository import CaseRepository

router = APIRouter()


# ── Response schemas ───────────────────────────────────────────────────────────

class StageEventOut(BaseModel):
    stage: str
    event_date: date
    confidence: float
    source_document_id: Optional[UUID]

    model_config = {"from_attributes": True}


class CaseOut(BaseModel):
    id: UUID
    crime_no: str
    date_reported: Optional[date]
    district_id: Optional[int]
    crime_head_id: Optional[int]
    case_status_id: Optional[int]
    source_type: str
    brief_facts: Optional[str] = None  # only included with Permission.VIEW_CASE_SENSITIVE
    version: int
    """Send this back unchanged in PATCH /{case_id} — see the optimistic-concurrency note there."""

    model_config = {"from_attributes": True}


class CaseUpdateRequest(BaseModel):
    version: int
    brief_facts: Optional[str] = None
    case_status_id: Optional[int] = None
    reason: Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{crime_no}", response_model=CaseOut)
async def get_case(
    crime_no: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CaseRepository(db)
    case = await repo.get_by_crime_no(crime_no, user=current_user)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    data = CaseOut.model_validate(case)
    if not role_has_permission(current_user.role, Permission.VIEW_CASE_SENSITIVE):
        data.brief_facts = None

    await log_audit_event(db, action="case.view", resource_type="case_master", resource_id=str(case.id))
    return data


@router.get("/", response_model=List[CaseOut])
async def list_cases(
    district_id: Optional[int] = Query(None),
    crime_head_id: Optional[int] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CaseRepository(db)
    start = start_date or date(2000, 1, 1)
    end = end_date or date.today()
    cases = await repo.search_by_date_range(
        start, end, district_id, crime_head_id, skip, limit, user=current_user
    )
    return [CaseOut.model_validate(c) for c in cases]


@router.patch("/{case_id}", response_model=CaseOut)
async def update_case(
    case_id: UUID,
    payload: CaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.EDIT_CASE)),
):
    """
    Edits brief_facts/case_status_id under optimistic concurrency control — the
    caller must send back the `version` it last read via GET /{crime_no}. A stale
    version returns 409 so the client can reload rather than silently clobbering
    a concurrent edit (the Investigator Workspace is explicitly multi-user).
    Every field change is captured automatically in RecordChangeHistory.
    """
    repo = CaseRepository(db)
    changes = {k: v for k, v in payload.model_dump(exclude={"version", "reason"}).items() if v is not None}
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    change_reason_ctx.set(payload.reason)
    updated = await repo.update_with_version(case_id, payload.version, changes)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Case has changed since you loaded it — reload and retry",
        )

    await log_audit_event(
        db, action="case.edited", resource_type="case_master", resource_id=str(case_id),
        payload=changes, reason=payload.reason,
    )
    data = CaseOut.model_validate(updated)
    if not role_has_permission(current_user.role, Permission.VIEW_CASE_SENSITIVE):
        data.brief_facts = None
    return data


@router.get("/{case_id}/stages", response_model=List[StageEventOut])
async def get_case_stages(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CaseRepository(db)
    # Verify the caller can see this case at all before returning its stage events.
    # CaseStageEvent has no RLS policy of its own, so we guard at the service layer.
    from sqlalchemy import select as _select
    from app.models.case import CaseMaster
    scoped_check = repo.scope_to_user(_select(CaseMaster.id).where(CaseMaster.id == case_id), current_user)
    check_result = await db.execute(scoped_check)
    if check_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Case not found")

    events = await repo.get_stage_events(case_id)
    return [StageEventOut.model_validate(e) for e in events]


@router.get("/{case_id}/brief", response_model=dict)
async def get_case_brief(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.GENERATE_CASE_BRIEF)),
):
    """One-click investigator case brief — fires the four-subagent fan-out."""
    from app.services.investigator_support import InvestigatorSupportService

    svc = InvestigatorSupportService(db)
    brief = await svc.generate_case_brief(case_id)
    await log_audit_event(db, action="case.ai_brief_generated", resource_type="case_master", resource_id=str(case_id))
    return brief
