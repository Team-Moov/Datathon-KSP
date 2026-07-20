"""
Person ORM models.
Three separate tables mirror the real KSP schema (Accused, Victim, ComplainantDetails).
PersonCaseRole is the cross-case identity join our entity-resolution layer writes to.

SENSITIVE-FIELD NOTE (§3.3):
  ComplainantDetails.ReligionID and ComplainantDetails.CasteID are explicitly named here.
  Any read of these columns MUST go through an access-control check at the service layer.
  These columns are NEVER used as model features in risk scoring (§7.3).
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
from app.models.enums import PersonRole, Sex


# ── Lookup tables ─────────────────────────────────────────────────────────────

class ReligionMaster(Base):
    __tablename__ = "religion_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class CasteMaster(Base):
    __tablename__ = "caste_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class OccupationMaster(Base):
    __tablename__ = "occupation_master"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)


# ── Unified Person entity (our entity-resolution output) ─────────────────────

class Person(Base):
    """
    Resolved, cross-case person identity.
    One row per unique real-world individual — NOT one row per FIR appearance.
    Entity resolution merges Accused / Victim / Complainant rows here.
    """

    __tablename__ = "person"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    aliases: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String), default=list)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    age_at_registration: Mapped[Optional[int]] = mapped_column(Integer)
    sex: Mapped[Optional[Sex]] = mapped_column(Enum(Sex))
    nationality: Mapped[Optional[str]] = mapped_column(String(100))
    permanent_address: Mapped[Optional[str]] = mapped_column(Text)
    present_address: Mapped[Optional[str]] = mapped_column(Text)
    occupation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("occupation_master.id"))

    # Provenance — which source record seeded this entity
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("document.id"))
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    """Optimistic-concurrency token — see CaseMaster.version."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    occupation: Mapped[Optional["OccupationMaster"]] = relationship()
    case_roles: Mapped[List["PersonCaseRole"]] = relationship(back_populates="person")
    criminal_history: Mapped[Optional["CriminalHistory"]] = relationship(  # type: ignore[name-defined]
        back_populates="person", uselist=False
    )


class PersonCaseRole(Base):
    """
    Join table: Person ↔ CaseMaster with role context.
    Replaces three separate KSP tables (Accused, Victim, ComplainantDetails)
    with a unified, cross-case identity model.

    SENSITIVE FIELDS:
      religion_id and caste_id are present only for complainants (matching real schema).
      These columns MUST NOT be exposed to roles < ANALYST, and MUST NOT feed model features.
    """

    __tablename__ = "person_case_role"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("person.id"), nullable=False, index=True)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_master.id"), nullable=False, index=True)
    role: Mapped[PersonRole] = mapped_column(Enum(PersonRole), nullable=False)

    # Arrest details (accused-specific)
    arrested: Mapped[bool] = mapped_column(Boolean, default=False)
    arrest_date: Mapped[Optional[date]] = mapped_column(Date)
    bail_granted: Mapped[Optional[bool]] = mapped_column(Boolean)

    # ── SENSITIVE FIELDS — complainant only ────────────────────────────────────
    # Access: role >= ANALYST only.  Never used as ML features (§7.3).
    religion_id: Mapped[Optional[int]] = mapped_column(ForeignKey("religion_master.id"))
    caste_id: Mapped[Optional[int]] = mapped_column(ForeignKey("caste_master.id"))
    # ──────────────────────────────────────────────────────────────────────────

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    person: Mapped["Person"] = relationship(back_populates="case_roles")
    case: Mapped["CaseMaster"] = relationship(back_populates="person_roles")  # type: ignore[name-defined]
    religion: Mapped[Optional["ReligionMaster"]] = relationship(foreign_keys=[religion_id])
    caste: Mapped[Optional["CasteMaster"]] = relationship(foreign_keys=[caste_id])
