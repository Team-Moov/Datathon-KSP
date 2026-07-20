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
        Main entry point. Returns a new RiskScore row (not yet committed).
        Caller is responsible for persisting after human review flag is set.
        """
        person = await self.person_repo.get_with_history(person_id)
        if person is None:
            return None

        # Check human_verified gate — history-sheet-derived data requires verification (§2.2)
        if person.criminal_history and not person.criminal_history.human_verified:
            log.warning(
                "Risk score blocked — criminal history not human-verified",
                person_id=str(person_id),
            )
            return None

        # ── Compute features ──────────────────────────────────────────────────
        chi_harm = await self._compute_chi_weighted_harm(person_id)
        network_centrality = await self._get_network_centrality(person_id)
        mo_escalation = await self._get_mo_escalation(person_id)
        associate_risk = await self._get_associate_risk_avg(person_id)

        # ── Weighted sum (logistic input) ─────────────────────────────────────
        # Weights are illustrative — real calibration requires labelled outcome data
        raw = (
            0.45 * min(chi_harm / 500.0, 1.0)
            + 0.25 * network_centrality
            + 0.15 * mo_escalation
            + 0.15 * min(associate_risk, 1.0)
        )
        score = round(1.0 / (1.0 + __import__("math").exp(-6 * (raw - 0.5))), 4)  # logistic

        # ── SHAP-style decomposition ──────────────────────────────────────────
        shap = {
            "chi_weighted_harm": round(0.45 * min(chi_harm / 500.0, 1.0), 4),
            "network_centrality": round(0.25 * network_centrality, 4),
            "mo_escalation": round(0.15 * mo_escalation, 4),
            "associate_risk": round(0.15 * min(associate_risk, 1.0), 4),
        }

        history = person.criminal_history
        if history is None:
            history = CriminalHistory(person_id=person_id, human_verified=False)
            self.db.add(history)
            await self.db.flush()
            await self.db.refresh(history)

        risk_row = RiskScore(
            criminal_history_id=history.id,
            model_version=MODEL_VERSION,
            score=score,
            chi_weighted_harm=chi_harm,
            network_centrality=network_centrality,
            mo_escalation_score=mo_escalation,
            associate_risk_avg=associate_risk,
            shap_decomposition=shap,
            human_reviewed=False,  # Must be set True by a human before surfacing
        )
        log.info(
            "Risk score computed",
            person_id=str(person_id),
            score=score,
            model_version=MODEL_VERSION,
        )
        return risk_row

    async def _compute_chi_weighted_harm(self, person_id: UUID) -> float:
        """
        CHI-weighted harm across person's incidents with recency decay (§7.4).
        Uses GravityOffence.chi_weight anchored to GravityOffenceID.
        """
        from sqlalchemy import text

        stmt = text("""
            SELECT
                cm.incident_from_date AS incident_date,
                COALESCE(go.chi_weight, 5.0) AS chi_weight
            FROM person_case_role pcr
            JOIN case_master cm ON cm.id = pcr.case_id
            LEFT JOIN gravity_offence go ON go.id = cm.gravity_offence_id
            WHERE pcr.person_id = :person_id
              AND pcr.role = :accused_role
        """)
        # SQLAlchemy's Enum column stores the Python member *name* ("ACCUSED"),
        # not PersonRole.ACCUSED.value ("accused") — the real Postgres enum
        # type only ever contains "ACCUSED"/"VICTIM"/etc. A raw 'accused'
        # literal here isn't just a non-match, it's an invalid enum literal
        # Postgres rejects outright (InvalidTextRepresentationError), which is
        # exactly what this call raised as a 500 the first time it ran live.
        result = await self.db.execute(
            stmt, {"person_id": str(person_id), "accused_role": PersonRole.ACCUSED.name}
        )
        rows = result.fetchall()

        today = date.today()
        total = 0.0
        for row in rows:
            incident_date = row[0]
            chi_weight = float(row[1] or 5.0)
            if incident_date:
                days_ago = (today - incident_date).days
                decay = 2 ** (-days_ago / DECAY_HALF_LIFE_DAYS)
            else:
                decay = 0.5
            total += chi_weight * decay

        return round(total, 4)

    async def _get_network_centrality(self, person_id: UUID) -> float:
        """Fetch pre-computed PageRank from graph store."""
        from app.core.graph_db import graph_db

        results = await graph_db.execute_query(
            "MATCH (p:Person {id: $id}) RETURN p.pagerank AS pr",
            {"id": str(person_id)},
        )
        if results:
            return float(results[0].get("pr") or 0.0)
        return 0.0

    async def _get_mo_escalation(self, person_id: UUID) -> float:
        """Placeholder — real impl computes trend in CHI weight across clusters."""
        return 0.0

    async def _get_associate_risk_avg(self, person_id: UUID) -> float:
        """Average risk score of direct graph neighbors (§7.4)."""
        from app.core.graph_db import graph_db
        from sqlalchemy import text

        # Get neighbor person IDs from graph
        results = await graph_db.execute_query(
            """
            MATCH (p:Person {id: $id})-[:ACCUSED_IN|ASSOCIATED_WITH]-(n:Person)
            RETURN n.id AS neighbor_id
            LIMIT 20
            """,
            {"id": str(person_id)},
        )
        neighbor_ids = [r["neighbor_id"] for r in results if r.get("neighbor_id")]
        if not neighbor_ids:
            return 0.0

        stmt = text("""
            SELECT AVG(rs.score) as avg_score
            FROM risk_score rs
            JOIN criminal_history ch ON ch.id = rs.criminal_history_id
            WHERE ch.person_id = ANY(:ids)
              AND rs.human_reviewed = true
        """)
        result = await self.db.execute(stmt, {"ids": neighbor_ids})
        avg = result.scalar_one_or_none()
        return float(avg or 0.0)
