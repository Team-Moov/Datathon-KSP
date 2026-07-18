"""Immutable audit log — every sensitive action recorded."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    """
    Append-only audit trail for all data access and mutations.
    Satisfies §10 accountability requirements and Explainable AI (§11).
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(200))
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class RecordChangeHistory(Base):
    """
    Immutable field-level change log for direct user edits to CaseMaster/Person/
    PersonCaseRole/User (§ Enterprise Security & Governance — Immutable Change History).
    Populated automatically by app.core.change_tracking's before_flush listener —
    never written to directly, never updated once inserted.

    Deliberately distinct from the design doc's versioned-derived-data pattern
    (RiskScore, MOLinkageCluster, predicted network links, §7.4/§11) — those are
    insert-only model outputs with their own model_version/computed_at columns.
    This table is for edits a human makes to a record that already exists.
    """

    __tablename__ = "record_change_history"
    __table_args__ = (
        Index("ix_record_change_history_table_record", "table_name", "record_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_name: Mapped[str] = mapped_column(String(100), nullable=False)
    record_id: Mapped[str] = mapped_column(String(200), nullable=False)
    field_name: Mapped[str] = mapped_column(String(200), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user.id"), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(500))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
