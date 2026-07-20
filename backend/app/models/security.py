"""
Session/MFA infrastructure (§ Enterprise Security & Governance — Multi-Factor
Authentication, session expiration). Platform infrastructure only — see
Part 0 of the design plan for why this sits alongside, not inside, the crime-domain
schema in karnataka_crime_platform_design.md.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OtpChallenge(Base):
    """
    One-time login challenge. `code_hash` never stores the plaintext code —
    only mfa_service's in-process return value (gated by ALLOW_MOCK_MFA) ever
    sees the plaintext, and only until real delivery is wired in.
    """

    __tablename__ = "otp_challenge"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(50), nullable=False, default="login")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RefreshTokenRecord(Base):
    """
    Server-side allowlist for issued refresh tokens. JWTs are stateless by
    default, which means a stolen/misused refresh token can't actually be
    revoked without this — logout, and "session expiration" as anything more
    than a client-side timer, both depend on this table existing.
    """

    __tablename__ = "refresh_token_record"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
