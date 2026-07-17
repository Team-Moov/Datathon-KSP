"""
Offender risk profiling and MO-linkage models (§7, §8.3).
All derived data is versioned — never overwrites history.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CriminalHistory(Base):
    """
    Aggregated history per person.
    chi_weighted_harm and network_centrality are recomputed by tools — never free-form.
    """

    __tablename__ = "criminal_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person.id"), nullable=False, unique=True, index=True
    )
    prior_incident_ids: Mapped[List[str]] = mapped_column(
        # stored as array of UUID strings for portability
        __import__("sqlalchemy").dialects.postgresql.ARRAY(String),
        default=list,
    )
    mo_pattern_summary: Mapped[Optional[str]] = mapped_column(Text)
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    """Must be True before risk score is surfaced to any role < ANALYST."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    person: Mapped["Person"] = relationship(back_populates="criminal_history")  # type: ignore[name-defined]
    risk_scores: Mapped[List["RiskScore"]] = relationship(back_populates="criminal_history")


class RiskScore(Base):
    """
    Versioned risk-score record (§7.4).
    Never overwrites; new assessment = new row.
    Each row includes the full SHAP-style feature decomposition.
    """

    __tablename__ = "risk_score"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    criminal_history_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("criminal_history.id"), nullable=False, index=True
    )
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)

    # Feature values used to produce this score
    chi_weighted_harm: Mapped[float] = mapped_column(Float, default=0.0)
    network_centrality: Mapped[float] = mapped_column(Float, default=0.0)
    mo_escalation_score: Mapped[float] = mapped_column(Float, default=0.0)
    associate_risk_avg: Mapped[float] = mapped_column(Float, default=0.0)

    # SHAP-style decomposition — {feature_name: contribution_value}
    shap_decomposition: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)

    human_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    criminal_history: Mapped["CriminalHistory"] = relationship(back_populates="risk_scores")


class MOLinkageCluster(Base):
    """
    Versioned MO-linkage cluster assignment per offense (§8.3).
    Never a static field bolted onto Offense — kept separate and versioned.
    """

    __tablename__ = "mo_linkage_cluster"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_master.id"), nullable=False, index=True)
    cluster_id: Mapped[str] = mapped_column(String(100), nullable=False)
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
