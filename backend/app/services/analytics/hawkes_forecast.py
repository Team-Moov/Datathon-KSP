"""
Crime Pattern & Trend Analytics — Hawkes/ETAS spatio-temporal point process (§5).
Deterministic tool — the LLM narrates the output, never produces the forecast itself.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


@dataclass
class GridCell:
    lat_min: float
    lat_max: float
    lng_min: float
    lng_max: float
    lat_center: float
    lng_center: float


@dataclass
class HawkesParameters:
    """Fitted ETAS model parameters."""
    mu: float           # background rate
    alpha: float        # triggering amplitude
    beta: float         # temporal decay rate
    sigma: float        # spatial kernel bandwidth (km)


@dataclass
class ForecastResult:
    cell: GridCell
    predicted_rate: float          # events / day
    background_component: float    # chronic baseline
    near_repeat_component: float   # acute near-repeat elevation
    forecast_date: date


class HawkesETASService:
    """
    Self-exciting spatio-temporal point process (Hawkes/ETAS) for crime hotspot forecasting.
    Background rate accepts district stress index as covariate (§6.2 feed-forward integration).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def forecast(
        self,
        district_id: int,
        crime_head_id: int,
        target_date: date,
        grid_resolution_km: float = 1.0,
        district_stress_index: Optional[float] = None,
    ) -> List[ForecastResult]:
        """
        Produce per-cell intensity forecasts for target_date.
        district_stress_index (from SocioEconomicIndicator) adjusts background rate (§6.2).
        """
        # 1. Load historical incidents for parameter fitting
        incidents = await self._load_incidents(district_id, crime_head_id, target_date)

        if len(incidents) < 10:
            log.warning(
                "Insufficient data for Hawkes fit",
                district_id=district_id,
                n_incidents=len(incidents),
            )
            return []

        # 2. Fit ETAS parameters via MLE (simplified)
        params = self._fit_etas(incidents)

        # 3. Apply district stress covariate to background rate
        if district_stress_index is not None:
            params.mu *= (1.0 + 0.1 * district_stress_index)  # linear adjustment

        # 4. Build grid over district bounding box
        bbox = self._get_bounding_box(incidents)
        cells = self._build_grid(bbox, grid_resolution_km)

        # 5. Compute per-cell intensity
        results = []
        for cell in cells:
            rate, bg, nr = self._compute_intensity(cell, incidents, params, target_date)
            results.append(
                ForecastResult(
                    cell=cell,
                    predicted_rate=round(rate, 6),
                    background_component=round(bg, 6),
                    near_repeat_component=round(nr, 6),
                    forecast_date=target_date,
                )
            )

        log.info(
            "Hawkes forecast complete",
            district_id=district_id,
            cells=len(results),
            target_date=str(target_date),
        )
        return results

    async def get_mo_linkage_clusters(
        self,
        crime_head_id: int,
        min_similarity: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """
        MO-based crime linkage via Jaccard similarity over structured MO features (§5).
        Returns candidate series clusters — labeled as plausible, not confirmed.
        """
        stmt = text("""
            SELECT c.cluster_id, count(c.id) as case_count, avg(c.similarity_score) as avg_similarity
            FROM mo_linkage_cluster c
            JOIN case_master cm ON cm.id = c.case_id
            WHERE cm.crime_head_id = :crime_head_id
              AND c.similarity_score >= :min_similarity
            GROUP BY c.cluster_id
            ORDER BY case_count DESC
        """)
        result = await self.db.execute(
            stmt, 
            {"crime_head_id": crime_head_id, "min_similarity": min_similarity}
        )
        return [dict(row._mapping) for row in result.fetchall()]

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _load_incidents(
        self, district_id: int, crime_head_id: int, before_date: date
    ) -> List[Dict[str, Any]]:
        """Load geo-timestamped incidents for fitting."""
        # Coerce a string date (some call paths pass ISO strings) so asyncpg can bind it.
        if isinstance(before_date, str):
            before_date = date.fromisoformat(before_date)
        stmt = text("""
            SELECT id, latitude, longitude, date_reported
            FROM case_master
            WHERE district_id = :district_id
              AND crime_head_id = :crime_head_id
              AND date_reported < :before_date
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
            ORDER BY date_reported ASC
        """)
        result = await self.db.execute(
            stmt,
            {
                "district_id": district_id,
                "crime_head_id": crime_head_id,
                "before_date": before_date,
            },
        )
        incidents = []
        for row in result.fetchall():
            m = dict(row._mapping)
            # Postgres Numeric → Decimal; numpy trig (radians) can't consume Decimal.
            m["latitude"] = float(m["latitude"]) if m["latitude"] is not None else None
            m["longitude"] = float(m["longitude"]) if m["longitude"] is not None else None
            incidents.append(m)
        return incidents

    def _fit_etas(self, incidents: List[Dict]) -> HawkesParameters:
        """
        Simplified MLE fit — production should use tick library or hawkeslib.
        Returns defensible default parameters on small samples.
        """
        n = len(incidents)
        if n < 20:
            return HawkesParameters(mu=0.1, alpha=0.5, beta=1.0, sigma=0.5)

        # Empirical background rate = events / time span
        dates = sorted(inc["date_reported"] for inc in incidents if inc["date_reported"])
        if len(dates) < 2:
            return HawkesParameters(mu=0.1, alpha=0.5, beta=1.0, sigma=0.5)

        span_days = max((dates[-1] - dates[0]).days, 1)
        mu = n / span_days

        return HawkesParameters(mu=mu, alpha=0.3, beta=0.8, sigma=1.0)

    def _compute_intensity(
        self,
        cell: GridCell,
        incidents: List[Dict],
        params: HawkesParameters,
        target_date: date,
    ) -> Tuple[float, float, float]:
        """λ(x, t) = μ(x) + Σ_j α · exp(-β(t-t_j)) · K_σ(x-x_j)."""
        background = params.mu
        near_repeat = 0.0

        for inc in incidents:
            if not (inc.get("latitude") and inc.get("longitude") and inc.get("date_reported")):
                continue

            dt = (target_date - inc["date_reported"]).days
            if dt < 0 or dt > 30:  # only look back 30 days for near-repeat
                continue

            # Temporal decay
            temporal = params.alpha * np.exp(-params.beta * dt)
            # Spatial Gaussian kernel
            dx = (inc["latitude"] - cell.lat_center) * 111.0  # degrees → km approx
            dy = (inc["longitude"] - cell.lng_center) * 111.0 * np.cos(np.radians(cell.lat_center))
            dist = np.sqrt(dx**2 + dy**2)
            spatial = np.exp(-(dist**2) / (2 * params.sigma**2))

            near_repeat += temporal * spatial

        total = background + near_repeat
        return total, background, near_repeat

    @staticmethod
    def _get_bounding_box(incidents: List[Dict]) -> Dict[str, float]:
        lats = [i["latitude"] for i in incidents if i.get("latitude")]
        lngs = [i["longitude"] for i in incidents if i.get("longitude")]
        return {
            "lat_min": min(lats), "lat_max": max(lats),
            "lng_min": min(lngs), "lng_max": max(lngs),
        }

    @staticmethod
    def _build_grid(bbox: Dict[str, float], resolution_km: float) -> List[GridCell]:
        """Subdivide bounding box into resolution_km × resolution_km cells."""
        cells = []
        deg_per_km_lat = 1.0 / 111.0
        deg_per_km_lng = 1.0 / (111.0 * np.cos(np.radians((bbox["lat_min"] + bbox["lat_max"]) / 2)))

        step_lat = resolution_km * deg_per_km_lat
        step_lng = resolution_km * deg_per_km_lng

        lat = bbox["lat_min"]
        while lat < bbox["lat_max"]:
            lng = bbox["lng_min"]
            while lng < bbox["lng_max"]:
                cells.append(GridCell(
                    lat_min=lat, lat_max=lat + step_lat,
                    lng_min=lng, lng_max=lng + step_lng,
                    lat_center=lat + step_lat / 2,
                    lng_center=lng + step_lng / 2,
                ))
                lng += step_lng
            lat += step_lat

        return cells
