"""
Administration endpoints (§ Enterprise Security & Governance — Audit Trail
viewer, user/role management). Read access (audit log) is broader than write
access (user management) — see the per-route Permission gate.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.enums import Role
from app.models.user import User
from app.repositories.user_repository import UserRepository

router = APIRouter()


class AuditLogOut(BaseModel):
    id: UUID
    user_id: Optional[UUID]
    action: str
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    reason: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: Role
    is_active: bool
    badge_number: Optional[str]
    district_id: Optional[int]
    unit_id: Optional[int]

    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Role
    badge_number: Optional[str] = None
    district_id: Optional[int] = None
    unit_id: Optional[int] = None


class UserRoleUpdateRequest(BaseModel):
    role: Role


@router.get("/audit-log", response_model=List[Dict[str, Any]])
async def list_audit_log(
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOG)),
):
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    if resource_id:
        filters.append(AuditLog.resource_id == resource_id)

    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    for f in filters:
        stmt = stmt.where(f)

    result = await db.execute(stmt)
    return [
        {
            "id": str(entry.id),
            "user_id": str(entry.user_id) if entry.user_id else None,
            "action": entry.action,
            "resource_type": entry.resource_type,
            "resource_id": entry.resource_id,
            "ip_address": entry.ip_address,
            "user_agent": entry.user_agent,
            "reason": entry.reason,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in result.scalars().all()
    ]


@router.get("/users", response_model=List[UserOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS)),
):
    result = await db.execute(select(User).order_by(User.full_name))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS)),
):
    repo = UserRepository(db)
    if await repo.get_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        badge_number=payload.badge_number,
        district_id=payload.district_id,
        unit_id=payload.unit_id,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    await log_audit_event(
        db, action="admin.user_created", resource_type="user", resource_id=str(user.id),
        payload={"role": payload.role.value},
    )
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}/role", response_model=UserOut)
async def update_user_role(
    user_id: UUID,
    payload: UserRoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS)),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    previous_role = user.role.value
    user.role = payload.role
    await db.flush()
    await log_audit_event(
        db, action="admin.user_role_changed", resource_type="user", resource_id=str(user_id),
        payload={"previous_role": previous_role, "new_role": payload.role.value},
    )
    return UserOut.model_validate(user)


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MANAGE_USERS)),
):
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.is_active = False
    await db.flush()
    await log_audit_event(db, action="admin.user_deactivated", resource_type="user", resource_id=str(user_id))
    return UserOut.model_validate(user)
