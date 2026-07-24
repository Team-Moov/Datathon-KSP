"""Crime pattern & trend analytics endpoints (§5)."""

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.models.user import User
from app.services.analytics.hawkes_forecast import HawkesETASService
from app.services.analytics.temporal_trends import TemporalTrendsService

router = APIRouter()


@router.get("/districts", response_model=List[Dict[str, Any]])
async def trends_districts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_TRENDS_HOTSPOTS)),
):
    """
    Named district list for this page's selector. Deliberately a separate
    endpoint from /socio/districts rather than pointing the Trends page at
    that one directly — /socio/districts requires VIEW_AGGREGATE_ANALYTICS,
    a higher tier than VIEW_TRENDS_HOTSPOTS (first granted at Constable), so
    reusing it here would silently 403 for exactly the roles who can already
    see hotspot forecasts. Same underlying data, just re-gated at the tier
    this page actually needs.
    """
    from app.services.analytics.socio_insights import SocioInsightsService

    svc = SocioInsightsService(db)
    return await svc.get_all_districts()


@router.get("/crime-heads", response_model=List[Dict[str, Any]])
async def trends_crime_heads(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_TRENDS_HOTSPOTS)),
):
    """Named crime-category list for this page's selector — no list endpoint
    for CrimeHead existed anywhere before this."""
    svc = HawkesETASService(db)
    return await svc.get_crime_heads()


@router.get("/hotspots", response_model=List[Dict[str, Any]])
async def forecast_hotspots(
    district_id: int = Query(...),
    crime_head_id: int = Query(...),
    target_date: date = Query(...),
    stress_index: Optional[float] = Query(None, description="District composite stress index covariate"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_TRENDS_HOTSPOTS)),
):
    """
    Hawkes/ETAS spatio-temporal forecast.
    Returns per-grid-cell predicted rates with background vs near-repeat decomposition.
    district_stress_index from SocioEconomicIndicator adjusts background rate (§6.2 integration).
    """
    svc = HawkesETASService(db)
    results = await svc.forecast(
        district_id=district_id,
        crime_head_id=crime_head_id,
        target_date=target_date,
        district_stress_index=stress_index,
    )
    return [
        {
            "lat_center": r.cell.lat_center,
            "lng_center": r.cell.lng_center,
            "predicted_rate": r.predicted_rate,
            "background_component": r.background_component,
            "near_repeat_component": r.near_repeat_component,
            "forecast_date": str(r.forecast_date),
        }
        for r in results
    ]


@router.get("/surveillance-priorities", response_model=Dict[str, Any])
async def surveillance_priorities(
    district_id: int = Query(...),
    crime_head_id: int = Query(...),
    target_date: date = Query(...),
    top_n: int = Query(10, ge=1, le=50),
    stress_index: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_TRENDS_HOTSPOTS)),
):
    """
    Top-N highest-risk grid cells from the real Hawkes/ETAS forecast, ranked
    and labeled as surveillance priority checkpoints. Not a patrol shift
    roster — see service docstring for why that's out of scope today.
    """
    svc = HawkesETASService(db)
    return await svc.get_surveillance_priorities(
        district_id=district_id,
        crime_head_id=crime_head_id,
        target_date=target_date,
        top_n=top_n,
        district_stress_index=stress_index,
    )


@router.get("/temporal", response_model=Dict[str, Any])
async def temporal_trends(
    district_id: int = Query(...),
    crime_head_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_TRENDS_HOTSPOTS)),
):
    """
    Real day-of-week, monthly seasonality, and (coverage-limited) hour-of-day
    breakdown from case_master's actual incident dates/times — not the Hawkes
    forecast, a separate direct aggregation.
    """
    svc = TemporalTrendsService(db)
    return await svc.get_temporal_trends(district_id=district_id, crime_head_id=crime_head_id)


@router.get("/mo-linkage/{crime_head_id}", response_model=List[Dict[str, Any]])
async def mo_linkage_clusters(
    crime_head_id: int,
    min_similarity: float = Query(0.7, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.VIEW_TRENDS_HOTSPOTS)),
):
    """
    Behavioral crime-series linkage (§5) from the trained MO-linkage model
    (`mo_linkage_tfidf_contrastive_v1`). Returns candidate series clusters for a
    crime head — plausible same-offender series, labeled as leads, never confirmed.
    This surfaces a model whose output was previously synced to the DB but
    unreachable from any endpoint or the UI.
    """
    svc = HawkesETASService(db)
    return await svc.get_mo_linkage_clusters(crime_head_id=crime_head_id, min_similarity=min_similarity)
