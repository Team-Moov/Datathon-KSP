"""Cases CRUD and stage-event endpoints."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.enums import CaseStage, Role
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
    source_type: str
    brief_facts: Optional[str] = None  # only included for ANALYST+

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{crime_no}", response_model=CaseOut)
async def get_case(
    crime_no: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CaseRepository(db)
    case = await repo.get_by_crime_no(crime_no)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    data = CaseOut.model_validate(case)
    # Restrict brief_facts to ANALYST and above
    if current_user.role in (Role.VIEWER,):
        data.brief_facts = None
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
    cases = await repo.search_by_date_range(start, end, district_id, crime_head_id, skip, limit)
    return [CaseOut.model_validate(c) for c in cases]


@router.get("/{case_id}/stages", response_model=List[StageEventOut])
async def get_case_stages(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = CaseRepository(db)
    events = await repo.get_stage_events(case_id)
    return [StageEventOut.model_validate(e) for e in events]


@router.get("/{case_id}/brief", response_model=dict)
async def get_case_brief(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.INVESTIGATOR, Role.ADMIN)),
):
    """One-click investigator case brief — fires the four-subagent fan-out."""
    from app.services.investigator_support import InvestigatorSupportService

    svc = InvestigatorSupportService(db)
    return await svc.generate_case_brief(case_id)
