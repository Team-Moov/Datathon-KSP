"""Risk profiling endpoints (§7)."""

from typing import Any, Dict
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.models.user import User
from app.services.analytics.risk_profiling import RiskProfilingService

router = APIRouter()


@router.post("/{person_id}/compute", response_model=Dict[str, Any])
async def compute_risk_score(
    person_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.COMPUTE_RISK_SCORE)),
):
    """
    Compute a new versioned risk score.
    Returns immediately — does NOT commit until human_reviewed is set.
    Blocked if criminal history is not human_verified (§2.2, §7.3).
    FAIRNESS NOTE: Protected attributes (ReligionID, CasteID) are never used as features.
    """
    svc = RiskProfilingService(db)
    score = await svc.compute_risk_score(person_id, current_user.role.value)

    if score is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Risk score blocked — criminal history not human-verified or person not found",
        )

    db.add(score)
    await db.flush()
    await db.refresh(score)

    return {
        "score_id": str(score.id),
        "person_id": str(person_id),
        "score": score.score,
        "model_version": score.model_version,
        "shap_decomposition": score.shap_decomposition,
        "human_reviewed": score.human_reviewed,
        "computed_at": str(score.computed_at),
        "disclaimer": (
            "Risk score is for investigative attention only. "
            "Human sign-off required before any operational decision. "
            "Protected demographic attributes were not used as features."
        ),
    }


@router.post("/{person_id}/scores/{score_id}/review", status_code=200)
async def mark_score_reviewed(
    person_id: UUID,
    score_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.REVIEW_RISK_SCORE)),
):
    """Human analyst signs off on the computed risk score."""
    from app.models.offender import RiskScore
    from sqlalchemy import select

    stmt = select(RiskScore).where(RiskScore.id == score_id)
    result = await db.execute(stmt)
    score = result.scalar_one_or_none()
    if not score:
        raise HTTPException(status_code=404, detail="Score not found")

    score.human_reviewed = True
    await db.flush()
    return {"status": "reviewed", "score_id": str(score_id), "reviewed_by": str(current_user.id)}
