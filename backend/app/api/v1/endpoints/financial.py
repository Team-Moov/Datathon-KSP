"""Financial crime detection endpoints (§9)."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.models.financial import FinancialTransaction
from app.models.user import User
from app.services.analytics.financial_crime import FinancialCrimeService

router = APIRouter()


@router.get("/accounts", response_model=List[Dict[str, Any]])
async def accounts_for_person(
    person_id: UUID = Query(..., description="Return the accounts appearing in this person's linked transactions."),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_FINANCIAL_RAW)),
):
    """
    The connective endpoint for the financial workflow: instead of typing an opaque
    account identifier, an investigator picks a person and gets the accounts tied to
    them (via FinancialTransaction.linked_person_id), each with an activity count and
    whether a typology alert already fired — ready to hand straight to /scan.
    """
    rows = (
        await db.execute(
            select(
                FinancialTransaction.from_account,
                FinancialTransaction.to_account,
                FinancialTransaction.alert_type,
            ).where(FinancialTransaction.linked_person_id == person_id)
        )
    ).all()

    accounts: Dict[str, Dict[str, Any]] = {}
    for from_account, to_account, alert_type in rows:
        for account in (from_account, to_account):
            if not account:
                continue
            entry = accounts.setdefault(account, {"account": account, "txn_count": 0, "flagged": False})
            entry["txn_count"] += 1
            if alert_type is not None:
                entry["flagged"] = True
    return sorted(accounts.values(), key=lambda a: (-a["txn_count"], a["account"]))


@router.get("/structuring/{account}", response_model=Optional[Dict[str, Any]])
async def detect_structuring(
    account: str,
    window_days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_FINANCIAL_RAW)),
):
    """Detect smurfing/structuring below ₹10 lakh CTR threshold."""
    svc = FinancialCrimeService(db)
    return await svc.detect_structuring(account, window_days)


@router.get("/funnel/{account}", response_model=Optional[Dict[str, Any]])
async def detect_funnel(
    account: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_FINANCIAL_RAW)),
):
    """Detect mule/funnel account pattern."""
    svc = FinancialCrimeService(db)
    return await svc.detect_funnel_account(account)


@router.get("/cycles", response_model=List[Dict[str, Any]])
async def detect_cycles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_FINANCIAL_RAW)),
):
    """Detect layering cycles in the TRANSACTED_WITH transaction graph."""
    svc = FinancialCrimeService(db)
    return await svc.detect_cycles_in_graph()


@router.post("/organized-clusters", response_model=List[Dict[str, Any]])
async def detect_organized_clusters(
    flagged_accounts: List[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_FINANCIAL_RAW)),
):
    """Community detection over already-flagged accounts -- surfaces
    organized rings rather than isolated structuring/funnel/layering hits."""
    svc = FinancialCrimeService(db)
    return await svc.detect_organized_clusters(flagged_accounts)


@router.post("/scan", response_model=List[Dict[str, Any]])
async def run_full_scan(
    accounts: List[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_FINANCIAL_RAW)),
):
    """Runs every detector + the organized-cluster pass over a given account
    list in one call -- what the demo/UI should actually hit."""
    svc = FinancialCrimeService(db)
    return await svc.run_full_scan(accounts)
