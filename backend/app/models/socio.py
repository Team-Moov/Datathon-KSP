"""
Sociological / aggregate data models (§6).
HARD RULE: These tables NEVER join to Person or PersonCaseRole.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SocioEconomicIndicator(Base):
    """
    District-year grain socio-economic data. Source: Census, NFHS, data.gov.in (§2.3).
    Used ONLY for place-level analysis — never joined to individual person records (§6.1).
    """

    __tablename__ = "socio_economic_indicator"
    __table_args__ = (UniqueConstraint("district_id", "year", name="uq_sei_district_year"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)

    literacy_rate: Mapped[float | None] = mapped_column(Float)
    unemployment_rate: Mapped[float | None] = mapped_column(Float)
    urbanization_pct: Mapped[float | None] = mapped_column(Float)
    population_density: Mapped[float | None] = mapped_column(Float)
    sex_ratio: Mapped[float | None] = mapped_column(Float)
    """Female per 1000 males — Census definition."""

    # Composite PCA index (computed periodically, stored as reference artifact)
    composite_stress_index: Mapped[float | None] = mapped_column(Float)
    composite_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CrimeStatAggregate(Base):
    """
    District-year-crime_head aggregate counts. Source: NCRB, data.gov.in (§2.3).
    """

    __tablename__ = "crime_stat_aggregate"
    __table_args__ = (
        UniqueConstraint("district_id", "year", "crime_head_id", name="uq_csa_district_year_head"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    crime_head_id: Mapped[int] = mapped_column(ForeignKey("crime_head.id"), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chi_weighted_count: Mapped[float | None] = mapped_column(Float)
    """Pre-computed CHI-weighted count — reused by Hawkes background-rate term (§6.2)."""


class DistrictCompositeIndex(Base):
    """
    Versioned GWR / regression outputs per district (§6.2).
    Stored as reference artifacts — not recomputed per query.
    """

    __tablename__ = "district_composite_index"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district_id: Mapped[int] = mapped_column(ForeignKey("district.id"), nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    run_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_version: Mapped[str] = mapped_column(String(50), nullable=False)

    # GWR coefficients — one per factor, stored as JSONB for flexibility
    gwr_coefficients: Mapped[dict] = mapped_column(JSONB, nullable=False)
    """{"unemployment": 0.32, "literacy": -0.18, ...} — locally varying coefficients."""

    composite_score: Mapped[float | None] = mapped_column(Float)
