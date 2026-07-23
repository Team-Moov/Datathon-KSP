"""
Sociological insights — read queries over SocioEconomicIndicator /
CrimeStatAggregate / DistrictCompositeIndex (§6).

ARCHITECTURAL RULE: never joins to Person or PersonCaseRole — place-level
only (§6.1). Factored out of app/api/v1/endpoints/socio.py so the same query
logic backs both the REST routes and the conversation-service LLM tools,
rather than duplicating it at each call site.
"""

import math
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.socio import CrimeStatAggregate, DistrictCompositeIndex, SocioEconomicIndicator
from app.models.unit import District


def _sanitize_score(value: Optional[float]) -> Optional[float]:
    """NaN/Inf aren't valid JSON (a literal NaN token fails JSON.parse on the
    frontend) — a local GWR fit can still produce one from a historical run
    predating the compute job's own NaN guard, so this defends the read path
    too, not just the write path in gwr.py."""
    if value is None:
        return None
    if math.isnan(value) or math.isinf(value):
        return None
    return value


class SocioInsightsService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_indicators(
        self, district_id: int, year_from: Optional[int] = None, year_to: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        filters = [SocioEconomicIndicator.district_id == district_id]
        if year_from:
            filters.append(SocioEconomicIndicator.year >= year_from)
        if year_to:
            filters.append(SocioEconomicIndicator.year <= year_to)

        stmt = select(SocioEconomicIndicator).where(*filters).order_by(SocioEconomicIndicator.year)
        rows = (await self.db.execute(stmt)).scalars().all()
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

    async def get_crime_stats(
        self, district_id: int, year: Optional[int] = None, crime_head_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        filters = [CrimeStatAggregate.district_id == district_id]
        if year:
            filters.append(CrimeStatAggregate.year == year)
        if crime_head_id:
            filters.append(CrimeStatAggregate.crime_head_id == crime_head_id)

        stmt = select(CrimeStatAggregate).where(*filters)
        rows = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "year": r.year,
                "crime_head_id": r.crime_head_id,
                "count": r.count,
                "chi_weighted_count": r.chi_weighted_count,
            }
            for r in rows
        ]

    async def get_all_districts_latest_gwr(self) -> List[Dict[str, Any]]:
        """
        One row per district from the most recent GWR batch run (see
        app/services/analytics/gwr.py), with each district's centroid —
        derived from CaseMaster.latitude/longitude, the same source the
        compute job itself uses — so the frontend can plot a centroid-marker
        map without needing district-boundary polygon data this platform
        doesn't have.
        """
        latest_run = (await self.db.execute(select(func.max(DistrictCompositeIndex.run_timestamp)))).scalar_one_or_none()
        if latest_run is None:
            return []

        rows = (
            await self.db.execute(
                select(DistrictCompositeIndex, District.name)
                .join(District, District.id == DistrictCompositeIndex.district_id)
                .where(DistrictCompositeIndex.run_timestamp == latest_run)
            )
        ).all()

        centroid_rows = (
            await self.db.execute(
                text(
                    "SELECT district_id, AVG(latitude) AS lat, AVG(longitude) AS lon "
                    "FROM case_master WHERE district_id IS NOT NULL AND latitude IS NOT NULL "
                    "GROUP BY district_id"
                )
            )
        ).all()
        centroids = {row.district_id: (float(row.lat), float(row.lon)) for row in centroid_rows}

        results = []
        for index_row, district_name in rows:
            centroid = centroids.get(index_row.district_id)
            results.append({
                "district_id": index_row.district_id,
                "district_name": district_name,
                "model_version": index_row.model_version,
                "run_timestamp": str(index_row.run_timestamp),
                "gwr_coefficients": index_row.gwr_coefficients,
                "composite_score": _sanitize_score(index_row.composite_score),
                "lat": centroid[0] if centroid else None,
                "lon": centroid[1] if centroid else None,
            })
        return results

    async def get_gwr_outputs(self, district_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Latest GWR coefficient runs for a district (§6.2), most recent first."""
        stmt = (
            select(DistrictCompositeIndex)
            .where(DistrictCompositeIndex.district_id == district_id)
            .order_by(DistrictCompositeIndex.run_timestamp.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return [
            {
                "model_version": r.model_version,
                "run_timestamp": str(r.run_timestamp),
                "data_version": r.data_version,
                "gwr_coefficients": r.gwr_coefficients,
                "composite_score": _sanitize_score(r.composite_score),
            }
            for r in rows
        ]
