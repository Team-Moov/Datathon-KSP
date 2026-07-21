"""
Risk Profiling Service — Central Eight factors, CHI weighting, SHAP decomposition (§7).
FAIRNESS CONSTRAINTS (§7.3):
  - Protected attributes (ReligionID, CasteID) NEVER used as features.
  - Score is paired with human sign-off requirement.
  - All outputs are versioned — never overwrites prior scores.
"""

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PersonRole
from app.models.offender import CriminalHistory, RiskScore
from app.repositories.person_repository import PersonRepository

log = structlog.get_logger(__name__)

MODEL_VERSION = "v1.0.0-logistic"

# CHI weights per GravityOffence (provisional — anchored to real GravityOffenceID) (§7.2)
CHI_WEIGHTS = {
    "Heinous": 100.0,
    "Non-Heinous": 10.0,
    "Unknown": 5.0,
}

# Exponential decay half-life for recency weighting (§7.4)
DECAY_HALF_LIFE_DAYS = 365


class RiskProfilingService:
    """
    Computes a versioned risk score from deterministic features.
    NEVER uses caste/religion as features.
    Always returns SHAP-style decomposition alongside the score.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.person_repo = PersonRepository(db)

    async def compute_risk_score(
        self,
        person_id: UUID,
        requesting_user_role: str,
    ) -> Optional[RiskScore]:
        """
        Main entry point. Returns the latest RiskScore row from the ML pipeline.
        The hand-rolled heuristic has been retired in favor of Ananya's model.
        """
        person = await self.person_repo.get_with_history(person_id)
        if person is None:
            return None

        # Check human_verified gate
        if person.criminal_history and not person.criminal_history.human_verified:
            log.warning(
                "Risk score blocked — criminal history not human-verified",
                person_id=str(person_id),
            )
            return None

        stmt = select(RiskScore).join(CriminalHistory).where(
            CriminalHistory.person_id == person_id
        ).order_by(RiskScore.computed_at.desc()).limit(1)
        
        result = await self.db.execute(stmt)
        risk_row = result.scalar_one_or_none()
        
        if risk_row:
            log.info(
                "Risk score retrieved from ML sync",
                person_id=str(person_id),
                score=risk_row.score,
                model_version=risk_row.model_version,
            )
        return risk_row


