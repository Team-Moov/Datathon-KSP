"""
Administration endpoints (§ Enterprise Security & Governance — Audit Trail
viewer, user/role management). Read access (audit log) is broader than write
access (user management) — see the per-route Permission gate.
"""

import re
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, field_validator
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
    id: str
    user_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    reason: Optional[str]
    # DEBT-05 fix: was `str` (unused because the endpoint returned Dict and called
    # .isoformat() manually). Now correctly typed as datetime so Pydantic
    # serializes it consistently and the type appears correctly in OpenAPI.
    created_at: datetime

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



_PASSWORD_RE = re.compile(
    r"^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*()_+\-=\[\]{};':""\\|,.<>\/?]).{10,}$"
)


def _validate_password_complexity(v: str) -> str:
    if not _PASSWORD_RE.match(v):
        raise ValueError(
            "Password must be at least 10 characters and contain at least one "
            "uppercase letter, one digit, and one special character"
        )
    return v


class UserCreateRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: Role
    badge_number: Optional[str] = None
    district_id: Optional[int] = None
    unit_id: Optional[int] = None

    @field_validator("password")
    @classmethod
    def _password_complexity(cls, v: str) -> str:
        return _validate_password_complexity(v)


class UserRoleUpdateRequest(BaseModel):
    role: Role


@router.get("/audit-log", response_model=List[AuditLogOut])
async def list_audit_log(
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    resource_id: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AUDIT_LOG)),
):
    # Build filters first, then apply ordering + pagination — the previous order
    # (offset/limit before where) paged the full table, then filtered, which made
    # the limit/skip counts meaningless against a filtered result set.
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    stmt = stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(stmt)
    # DEBT-05 fix: AuditLogOut is now the actual response_model (was Dict[str, Any]).
    # Pydantic handles datetime serialization consistently; from_attributes=True
    # on the model means model_validate works directly from the ORM object.
    return [AuditLogOut.model_validate(entry) for entry in result.scalars().all()]


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
