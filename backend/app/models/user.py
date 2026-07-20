"""User model — RBAC roles: CONSTABLE, INSPECTOR, DSP, SP, DGP, CRIME_ANALYST, POLICY_MAKER."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Role


class User(Base):
    __tablename__ = "user"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(300), nullable=False)
    role: Mapped[Role] = mapped_column(Enum(Role), nullable=False, default=Role.CONSTABLE)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    badge_number: Mapped[str | None] = mapped_column(String(50), unique=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("unit.id"), nullable=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("district.id"), nullable=True)
    """Ranks below DSP are scoped to cases within their own district — see
    CaseRepository.scope_to_user. DSP and above see every district."""

    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
