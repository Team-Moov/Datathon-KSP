"""
Investigator Workspace endpoints (§ Enterprise Security & Governance —
Investigator Workspace) — one aggregated view per case, plus note CRUD.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.database import get_db
from app.core.permissions import Permission, require_permission, role_has_permission
from app.core.security import get_current_user
from app.models.user import User
from app.models.workspace import CaseNote
from app.repositories.base import BaseRepository
from app.services import workspace_service

router = APIRouter()


class NoteCreateRequest(BaseModel):
    content: str
    pinned: bool = False


class NoteUpdateRequest(BaseModel):
    version: int
    content: Optional[str] = None
    pinned: Optional[bool] = None


def _note_repo(db: AsyncSession) -> BaseRepository[CaseNote]:
    return BaseRepository(CaseNote, db)


@router.get("/cases/{case_id}", response_model=Dict[str, Any])
async def get_case_workspace(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workspace = await workspace_service.build_case_workspace(db, case_id, current_user)
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    await log_audit_event(db, action="case.workspace_view", resource_type="case_master", resource_id=str(case_id))
    return workspace


@router.get("/cases/{case_id}/notes", response_model=List[Dict[str, Any]])
async def list_case_notes(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import select

    stmt = select(CaseNote).where(CaseNote.case_id == case_id).order_by(CaseNote.pinned.desc(), CaseNote.updated_at.desc())
    result = await db.execute(stmt)
    return [workspace_service.serialize_note(n) for n in result.scalars().all()]


@router.post("/cases/{case_id}/notes", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_case_note(
    case_id: UUID,
    payload: NoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_CASE_SENSITIVE)),
):
    note = CaseNote(case_id=case_id, author_id=current_user.id, content=payload.content, pinned=payload.pinned)
    repo = _note_repo(db)
    created = await repo.create(note)
    await log_audit_event(db, action="case.note_added", resource_type="case_note", resource_id=str(created.id), payload={"case_id": str(case_id)})
    return workspace_service.serialize_note(created)


@router.patch("/cases/{case_id}/notes/{note_id}", response_model=Dict[str, Any])
async def update_case_note(
    case_id: UUID,
    note_id: UUID,
    payload: NoteUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = _note_repo(db)
    existing = await repo.get_by_id(note_id)
    if existing is None or existing.case_id != case_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if existing.author_id != current_user.id and not role_has_permission(current_user.role, Permission.MANAGE_CASE_NOTES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author (or SP/DGP) may edit this note")

    changes = {k: v for k, v in payload.model_dump(exclude={"version"}).items() if v is not None}
    updated = await repo.update_with_version(note_id, payload.version, changes)
    if updated is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Note has changed since you loaded it — reload and retry")
    return workspace_service.serialize_note(updated)


@router.delete("/cases/{case_id}/notes/{note_id}", status_code=status.HTTP_200_OK)
async def delete_case_note(
    case_id: UUID,
    note_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = _note_repo(db)
    existing = await repo.get_by_id(note_id)
    if existing is None or existing.case_id != case_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    if existing.author_id != current_user.id and not role_has_permission(current_user.role, Permission.MANAGE_CASE_NOTES):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author (or SP/DGP) may delete this note")

    await repo.delete(existing)
    await log_audit_event(db, action="case.note_deleted", resource_type="case_note", resource_id=str(note_id), payload={"case_id": str(case_id)})
    return {"status": "deleted", "note_id": str(note_id)}
