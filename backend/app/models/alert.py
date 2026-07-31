"""
Early-warning Alert model (capability #8 — 'Crime Forecasting & Early Warning').

An Alert is a *derived* signal, produced by a deterministic detector in
EarlyWarningService, never by an LLM. Like every other derived-data table in this
platform (risk scores, predicted links, MO clusters) it carries its source tool
and a confidence, and it is versioned-by-signature rather than overwritten: the
`signature` is a deterministic fingerprint of the finding, uniquely constrained so
a repeated scan re-detecting the same condition does not pile up duplicate rows.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import AlertSeverity, AlertStatus, AlertType


class Alert(Base):
    __tablename__ = "alert"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False, index=True)
    severity: Mapped[AlertSeverity] = mapped_column(Enum(AlertSeverity), nullable=False, index=True)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus), nullable=False, default=AlertStatus.NEW, index=True
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Evidence trail (capability #9): the exact detector output that justifies this
    # alert — source_tool, the records involved, and the metric that tripped it.
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source_tool: Mapped[str] = mapped_column(String(120), nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Float)

    # Optional subject anchors — nullable because some alerts (e.g. an organized
    # group) are about a set of people, not a single one.
    district_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    subject_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("person.id"), nullable=True)
    subject_case_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("case_master.id"), nullable=True)

    # Deterministic de-dup key — unique so an idempotent re-scan is a no-op, not a
    # duplicate. Encodes detector + subject + the metric bucket that fired.
    signature: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)

    acknowledged_by: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("user.id"), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
