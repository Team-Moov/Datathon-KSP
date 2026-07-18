"""Persons endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.database import get_db
from app.core.masking import mask_address, mask_person_display_name
from app.core.permissions import Permission, require_permission, role_has_permission
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.person_repository import PersonRepository

router = APIRouter()


class PersonOut(BaseModel):
    id: UUID
    full_name: str
    aliases: Optional[List[str]]
    nationality: Optional[str]
    permanent_address: Optional[str]
    present_address: Optional[str]
    human_verified: bool
    version: int

    model_config = {"from_attributes": True}


class PersonVerifyRequest(BaseModel):
    version: int
    reason: Optional[str] = None


def _apply_pii_masking(data: PersonOut, current_user: User) -> PersonOut:
    has_permission = role_has_permission(current_user.role, Permission.VIEW_PII_UNMASKED)
    data.full_name = mask_person_display_name(data.full_name, has_permission)
    data.permanent_address = mask_address(data.permanent_address, has_permission)
    data.present_address = mask_address(data.present_address, has_permission)
    return data


@router.get("/search", response_model=List[PersonOut])
async def search_persons(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = PersonRepository(db)
    results = await repo.search_by_name(q)
    return [_apply_pii_masking(PersonOut.model_validate(p), current_user) for p in results]


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = PersonRepository(db)
    person = await repo.get_with_history(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return _apply_pii_masking(PersonOut.model_validate(person), current_user)


@router.post("/{person_id}/verify", response_model=PersonOut)
async def verify_person(
    person_id: UUID,
    payload: PersonVerifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VERIFY_PERSON)),
):
    """
    Human analyst verifies the entity-resolution result.
    Required before risk score is surfaced (§2.2, §7.3).
    Optimistic-concurrency checked the same way as case edits — see cases.update_case.
    """
    repo = PersonRepository(db)
    updated = await repo.update_with_version(person_id, payload.version, {"human_verified": True})
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Person record has changed since you loaded it — reload and retry",
        )

    await log_audit_event(
        db, action="person.verified", resource_type="person", resource_id=str(person_id),
        reason=payload.reason,
    )
    return PersonOut.model_validate(updated)
