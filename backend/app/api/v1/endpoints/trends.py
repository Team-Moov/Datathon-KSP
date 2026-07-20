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

router = APIRouter()


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
