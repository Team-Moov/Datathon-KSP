"""
Sociological insights endpoints (§6).
ARCHITECTURAL RULE: These endpoints read ONLY from SocioEconomicIndicator
and CrimeStatAggregate — never from Person or PersonCaseRole.
The query layer enforces this; it is also enforced at the service level
(app/services/analytics/socio_insights.py).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.models.user import User
from app.services.analytics.socio_insights import SocioInsightsService

router = APIRouter()


@router.get("/indicators/{district_id}", response_model=List[Dict[str, Any]])
async def get_socio_indicators(
    district_id: int,
    year_from: Optional[int] = Query(None),
    year_to: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """
    Socio-economic time series for a district.
    Place-level only — never joined to person data (§6.1 hard rule).
    """
    return await SocioInsightsService(db).get_indicators(district_id, year_from, year_to)


@router.get("/crime-stats/{district_id}", response_model=List[Dict[str, Any]])
async def get_crime_stats(
    district_id: int,
    year: Optional[int] = Query(None),
    crime_head_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """Aggregate crime counts by district-year-crime_head (§6 — CHI-weighted available)."""
    return await SocioInsightsService(db).get_crime_stats(district_id, year, crime_head_id)


@router.get("/gwr/{district_id}", response_model=List[Dict[str, Any]])
async def get_gwr_outputs(
    district_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """
    Latest GWR coefficient outputs for one district.
    Versioned — each run is a separate row (§6.2).
    """
    return await SocioInsightsService(db).get_gwr_outputs(district_id)


@router.get("/gwr-map", response_model=List[Dict[str, Any]])
async def get_gwr_map(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """
    Latest GWR run for every district at once, with centroid coordinates —
    powers the statewide map widget (centroid markers, not a polygon
    choropleth — this platform has no district-boundary geometry).
    """
    return await SocioInsightsService(db).get_all_districts_latest_gwr()


@router.get("/districts", response_model=List[Dict[str, Any]])
async def get_all_districts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """List all Karnataka districts with stress scores and centroid coordinates."""
    return await SocioInsightsService(db).get_all_districts()


@router.get("/correlations", response_model=Dict[str, Any])
async def get_socio_correlations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """Statewide correlation matrix: Socio-economic indicators vs CHI-weighted harm vs Raw counts."""
    return await SocioInsightsService(db).get_correlation_matrix()


@router.get("/demographics/victims", response_model=Dict[str, Any])
async def get_victim_demographics(
    district_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """Aggregate victim socio-demographics for police resource planning."""
    return await SocioInsightsService(db).get_victim_demographics(district_id)


@router.get("/urbanization-impact", response_model=List[Dict[str, Any]])
async def get_urbanization_impact(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """Urbanization growth vs crime trend velocity analysis."""
    return await SocioInsightsService(db).get_urbanization_impact()


@router.get("/policy-recommendations/{district_id}", response_model=Dict[str, Any])
async def get_policy_recommendations(
    district_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """Automated criminological diagnostic & policy intervention recommendations for a district."""
    return await SocioInsightsService(db).get_policy_recommendations(district_id)


@router.get("/calculate-staffing/{district_id}", response_model=Dict[str, Any])
async def calculate_police_staffing(
    district_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_AGGREGATE_ANALYTICS)),
):
    """Calculates recommended police staffing requirements for a district dynamically."""
    return await SocioInsightsService(db).calculate_police_staffing(district_id)


