"""
Organisational hierarchy models — mirrors KSP Unit/UnitType/District hierarchy (§3.3).
Unit.parent_unit_id self-reference models station → circle → district levels.
"""

from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class State(Base):
    __tablename__ = "state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(10))

    districts: Mapped[List["District"]] = relationship(back_populates="state")


class District(Base):
    __tablename__ = "district"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("state.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[Optional[str]] = mapped_column(String(20))

    state: Mapped["State"] = relationship(back_populates="districts")
    units: Mapped[List["Unit"]] = relationship(back_populates="district")


class UnitType(Base):
    """Encodes the jurisdictional hierarchy level (§3.3 — Unit.ParentUnit)."""

    __tablename__ = "unit_type"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "Police Station"
    hierarchy_level: Mapped[int] = mapped_column(Integer, nullable=False)
    """Lower number = higher in hierarchy (e.g. 1=Commissionerate, 3=Station)."""


class Unit(Base):
    """
    Police unit with self-referential parent (station → circle → district).
    Enables multi-jurisdiction detection: repeat offenders spanning units at different hierarchy
    levels is a signal of organized / mobile criminal activity (§3.3).
    """

    __tablename__ = "unit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    unit_type_id: Mapped[int] = mapped_column(ForeignKey("unit_type.id"), nullable=False)
    district_id: Mapped[Optional[int]] = mapped_column(ForeignKey("district.id"), nullable=True)
    parent_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unit.id"), nullable=True)

    unit_type: Mapped["UnitType"] = relationship()
    district: Mapped[Optional["District"]] = relationship(back_populates="units")
    parent: Mapped[Optional["Unit"]] = relationship("Unit", remote_side="Unit.id")
    children: Mapped[List["Unit"]] = relationship("Unit", back_populates="parent")


class Court(Base):
    __tablename__ = "court"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    district_id: Mapped[Optional[int]] = mapped_column(ForeignKey("district.id"))
    address: Mapped[Optional[str]] = mapped_column(Text)
