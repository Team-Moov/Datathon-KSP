"""
Document provenance model — the backbone of Explainable AI (§11).
Every fact that enters the system through ingestion is backed by a Document row.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DocumentFormat, ExtractionMethod, SourceType


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    source_type: Mapped[SourceType] = mapped_column(Enum(SourceType), nullable=False)
    file_format: Mapped[DocumentFormat] = mapped_column(
        Enum(DocumentFormat), default=DocumentFormat.UNKNOWN
    )
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_file_ref: Mapped[str] = mapped_column(String(1000), nullable=False)
    """Storage path or URI — never a direct file-system path exposed to client."""

    ingestion_ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod), nullable=False
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    """Extraction confidence [0, 1] — propagated to every fact derived from this document."""

    linked_incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("case_master.id"), nullable=True
    )
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    staging_only: Mapped[bool] = mapped_column(Boolean, default=False)
    """
    True for news articles — kept in staging, NEVER auto-merged into Incident (§2.2).
    Analyst must explicitly promote a staged document to verified status.
    """

    ingested_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("user.id"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text)
