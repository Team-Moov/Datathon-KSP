"""
Model transparency endpoints (capability #9 — Explainable AI & Transparent Analytics).

Surfaces every ML model's held-out quality metrics, feature importances, and
fairness posture. Available to any authenticated user — transparency is the point;
there is nothing role-sensitive about a model's concordance index or the fact that
protected attributes were never used as features.
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.models.user import User
from app.services.ml_registry import get_model_card, get_model_cards

router = APIRouter()


@router.get("/", response_model=List[Dict[str, Any]])
async def list_models(current_user: User = Depends(get_current_user)):
    """Every model card — version, task, primary metric, feature importance, fairness."""
    return get_model_cards()


@router.get("/{model_version}", response_model=Dict[str, Any])
async def get_model(model_version: str, current_user: User = Depends(get_current_user)):
    card = get_model_card(model_version)
    if card is None:
        raise HTTPException(status_code=404, detail=f"No model card for '{model_version}'")
    return card
