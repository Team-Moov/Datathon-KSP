"""Persons endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_roles
from app.models.enums import Role
from app.models.user import User
from app.repositories.person_repository import PersonRepository

router = APIRouter()


class PersonOut(BaseModel):
    id: UUID
    full_name: str
    aliases: Optional[List[str]]
    nationality: Optional[str]
    human_verified: bool

    model_config = {"from_attributes": True}


@router.get("/search", response_model=List[PersonOut])
async def search_persons(
    q: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = PersonRepository(db)
    return await repo.search_by_name(q)


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = PersonRepository(db)
    person = await repo.get_with_history(person_id)
    if not person:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Person not found")
    return PersonOut.model_validate(person)


@router.post("/{person_id}/verify", status_code=200)
async def verify_person(
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """
    Human analyst verifies the entity-resolution result.
    Required before risk score is surfaced (§2.2, §7.3).
    """
    repo = PersonRepository(db)
    person = await repo.get_by_id(person_id)
    if not person:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Person not found")
    person.human_verified = True
    await db.flush()
    return {"status": "verified", "person_id": str(person_id)}
