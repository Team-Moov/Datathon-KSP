"""
Sociological insights endpoints (§6).
ARCHITECTURAL RULE: These endpoints read ONLY from SocioEconomicIndicator
and CrimeStatAggregate — never from Person or PersonCaseRole.
The query layer enforces this; it is also enforced at the service level.
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import Role
from app.models.user import User
from app.models.socio import CrimeStatAggregate, DistrictCompositeIndex, SocioEconomicIndicator

router = APIRouter()


@router.get("/indicators/{district_id}", response_model=List[Dict[str, Any]])
async def get_socio_indicators(
    district_id: int,
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """
    Socio-economic time series for a district.
    Place-level only — never joined to person data (§6.1 hard rule).
    """
    filters = [SocioEconomicIndicator.district_id == district_id]
    if year_from:
        filters.append(SocioEconomicIndicator.year >= year_from)
    if year_to:
        filters.append(SocioEconomicIndicator.year <= year_to)

    stmt = select(SocioEconomicIndicator).where(*filters).order_by(SocioEconomicIndicator.year)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "year": r.year,
            "literacy_rate": r.literacy_rate,
            "unemployment_rate": r.unemployment_rate,
            "urbanization_pct": r.urbanization_pct,
            "sex_ratio": r.sex_ratio,
            "composite_stress_index": r.composite_stress_index,
        }
        for r in rows
    ]


@router.get("/crime-stats/{district_id}", response_model=List[Dict[str, Any]])
async def get_crime_stats(
    district_id: int,
    year: Optional[int] = Query(None),
    crime_head_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """Aggregate crime counts by district-year-crime_head (§6 — CHI-weighted available)."""
    filters = [CrimeStatAggregate.district_id == district_id]
    if year:
        filters.append(CrimeStatAggregate.year == year)
    if crime_head_id:
        filters.append(CrimeStatAggregate.crime_head_id == crime_head_id)

    stmt = select(CrimeStatAggregate).where(*filters)
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "year": r.year,
            "crime_head_id": r.crime_head_id,
            "count": r.count,
            "chi_weighted_count": r.chi_weighted_count,
        }
        for r in rows
    ]


@router.get("/gwr/{district_id}", response_model=List[Dict[str, Any]])
async def get_gwr_outputs(
    district_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ANALYST, Role.ADMIN)),
):
    """
    Latest GWR coefficient outputs for choropleth widget.
    Versioned — each run is a separate row (§6.2).
    """
    stmt = (
        select(DistrictCompositeIndex)
        .where(DistrictCompositeIndex.district_id == district_id)
        .order_by(DistrictCompositeIndex.run_timestamp.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [
        {
            "model_version": r.model_version,
            "run_timestamp": str(r.run_timestamp),
            "data_version": r.data_version,
            "gwr_coefficients": r.gwr_coefficients,
            "composite_score": r.composite_score,
        }
        for r in rows
    ]
