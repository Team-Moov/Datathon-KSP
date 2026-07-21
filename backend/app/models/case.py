"""
Case-level ORM models.
Mirrors the real KSP schema (CaseMaster, ActSectionAssociation, etc.)
with additions for poly-store integration (CaseStageEvent).
"""

import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CaseDispositionType, CaseStage, SourceType


# ── Reference / lookup tables ─────────────────────────────────────────────────

class CrimeHead(Base):
    __tablename__ = "crime_head"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(50), unique=True)

    sub_heads: Mapped[List["CrimeSubHead"]] = relationship(back_populates="crime_head")


class CrimeSubHead(Base):
    __tablename__ = "crime_sub_head"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    crime_head_id: Mapped[int] = mapped_column(ForeignKey("crime_head.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gravity_offence_id: Mapped[Optional[int]] = mapped_column(ForeignKey("gravity_offence.id"))

    crime_head: Mapped["CrimeHead"] = relationship(back_populates="sub_heads")
    gravity_offence: Mapped[Optional["GravityOffence"]] = relationship()


class GravityOffence(Base):
    __tablename__ = "gravity_offence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)  # Heinous / Non-Heinous
    chi_weight: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=1.0)
    """Crime Harm Index weight — sentencing-days-equivalent per offense type."""


class Act(Base):
    __tablename__ = "act"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column(String(50))


class Section(Base):
    __tablename__ = "section"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("act.id"), nullable=False)
    section_number: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    act: Mapped["Act"] = relationship()


class CaseStatusMaster(Base):
    __tablename__ = "case_status_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    status_name: Mapped[str] = mapped_column(String(100), nullable=False)


# ── Core case table (mirrors KSP CaseMaster) ─────────────────────────────────

class CaseMaster(Base):
    __tablename__ = "case_master"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # KSP CaseMaster fields
    crime_no: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    """Encoded as category+district+station+year per real KSP schema."""
    unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unit.id"))
    district_id: Mapped[Optional[int]] = mapped_column(ForeignKey("district.id"))

    incident_from_date: Mapped[Optional[date]] = mapped_column(Date)
    incident_to_date: Mapped[Optional[date]] = mapped_column(Date)
    date_reported: Mapped[Optional[date]] = mapped_column(Date, index=True)

    # Geography (from real schema)
    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))

    crime_head_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crime_head.id"))
    crime_sub_head_id: Mapped[Optional[int]] = mapped_column(ForeignKey("crime_sub_head.id"))
    gravity_offence_id: Mapped[Optional[int]] = mapped_column(ForeignKey("gravity_offence.id"))
    case_status_id: Mapped[Optional[int]] = mapped_column(ForeignKey("case_status_master.id"))

    brief_facts: Mapped[Optional[str]] = mapped_column(Text)
    """BriefFacts — the field embedded by the vector store (per reconciliation in §3.3)."""

    gd_number: Mapped[Optional[str]] = mapped_column(String(100))
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType), default=SourceType.FIR, nullable=False
    )

    # Provenance
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("document.id"))

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    """Optimistic-concurrency token — every PATCH must send back the version it
    read; a mismatch means someone else edited this case first (§ OCC)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    act_section_associations: Mapped[List["ActSectionAssociation"]] = relationship(
        back_populates="case"
    )
    chargesheet: Mapped[Optional["ChargesheetDetails"]] = relationship(
        back_populates="case", uselist=False
    )
    stage_events: Mapped[List["CaseStageEvent"]] = relationship(back_populates="case")
    person_roles: Mapped[List["PersonCaseRole"]] = relationship(back_populates="case")  # type: ignore[name-defined]
    document: Mapped[Optional["Document"]] = relationship(foreign_keys=[document_id])  # type: ignore[name-defined]


class ActSectionAssociation(Base):
    """Normalized many-to-many: Case ↔ Act+Section (mirrors KSP ActSectionAssociation)."""

    __tablename__ = "act_section_association"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_master.id"), nullable=False)
    act_id: Mapped[Optional[int]] = mapped_column(ForeignKey("act.id"), nullable=True)
    section_id: Mapped[Optional[int]] = mapped_column(ForeignKey("section.id"), nullable=True)

    case: Mapped["CaseMaster"] = relationship(back_populates="act_section_associations")
    act: Mapped["Act"] = relationship()
    section: Mapped["Section"] = relationship()


class ChargesheetDetails(Base):
    """Mirrors KSP ChargesheetDetails — cstype is the disposition signal (§3.3)."""

    __tablename__ = "chargesheet_details"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_master.id"), nullable=False, unique=True
    )
    cs_type: Mapped[CaseDispositionType] = mapped_column(Enum(CaseDispositionType), nullable=False)
    cs_date: Mapped[Optional[date]] = mapped_column(Date)
    court_id: Mapped[Optional[int]] = mapped_column(ForeignKey("court.id"))

    case: Mapped["CaseMaster"] = relationship(back_populates="chargesheet")


class CaseStageEvent(Base):
    """
    Tracks full status history — the real KSP schema stores only current status.
    Incident.status convenience property reflects the latest event. (§8.3)
    """

    __tablename__ = "case_stage_event"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_master.id"), nullable=False)
    stage: Mapped[CaseStage] = mapped_column(Enum(CaseStage), nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("document.id"), nullable=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    case: Mapped["CaseMaster"] = relationship(back_populates="stage_events")
