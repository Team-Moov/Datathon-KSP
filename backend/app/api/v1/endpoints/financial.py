"""Financial crime detection endpoints (§9)."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import Role
from app.models.user import User
from app.services.analytics.financial_crime import FinancialCrimeService

router = APIRouter()


@router.get("/structuring/{account}", response_model=Optional[Dict[str, Any]])
async def detect_structuring(
    account: str,
    window_days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """Detect smurfing/structuring below ₹10 lakh CTR threshold."""
    svc = FinancialCrimeService(db)
    return await svc.detect_structuring(account, window_days)


@router.get("/funnel/{account}", response_model=Optional[Dict[str, Any]])
async def detect_funnel(
    account: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """Detect mule/funnel account pattern."""
    svc = FinancialCrimeService(db)
    return await svc.detect_funnel_account(account)


@router.get("/cycles", response_model=List[Dict[str, Any]])
async def detect_cycles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """Detect layering cycles in the TRANSACTED_WITH transaction graph."""
    svc = FinancialCrimeService(db)
    return await svc.detect_cycles_in_graph()
