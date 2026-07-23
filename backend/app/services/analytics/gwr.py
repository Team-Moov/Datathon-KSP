"""
Geographically Weighted Regression — socio-economic factors vs. CHI-weighted
crime harm, per district (§6.2). Previously unimplemented: `mgwr` has been a
pinned dependency since early on, but nothing ever called it — the
`district_composite_index.gwr_coefficients` column and the `/socio/gwr/{id}`
endpoint existed with no writer (see DATA_AND_TESTING_REQUIREMENTS.md §11/§13).

GWR needs the FULL set of districts fit as one model — each district's local
coefficient comes from a spatial kernel over every other district's
observation — so this is a batch job over all qualifying districts, not a
per-district computation, unlike the other versioned-derived-data jobs in
this codebase (risk_score, mo_linkage_cluster) which score one entity at a
time.

Spatial coordinates are each district's centroid, computed as the mean of
CaseMaster.latitude/longitude for cases already assigned to it — reusing data
the platform already backfills (see scripts/ml_bridge/enrich.py) rather than
requiring a separate district-boundary/shapefile dependency.
"""

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.socio import CrimeStatAggregate, DistrictCompositeIndex, SocioEconomicIndicator

log = structlog.get_logger(__name__)

MODEL_VERSION = "gwr-mgwr-v1"
MIN_DISTRICTS_FOR_FIT = 5
# Correlate against CHI-weighted crime harm (design §7.2's severity anchor), not
# raw counts — five thefts and one attempted murder shouldn't weigh the same.
_FACTOR_COLUMNS = ["literacy_rate", "unemployment_rate", "urbanization_pct"]


def _safe_float(value: float) -> Optional[float]:
    """NaN/Inf are real possible outputs of a local GWR fit on a thin/near-
    singular neighborhood, but neither is valid JSON — Python's json module
    will happily emit a literal `NaN` token that then fails to parse on the
    receiving end (this broke the frontend's JSON.parse on the streamed chat
    event containing it). Store/serialize None instead."""
    if math.isnan(value) or math.isinf(value):
        return None
    return value


async def compute_all_districts_gwr(db: AsyncSession) -> Dict[str, Any]:
    """
    Fits one GWR model across every district with both a socio-indicator row
    and a derivable centroid, then writes one versioned DistrictCompositeIndex
    row per district (shared run_timestamp/model_version/data_version for the
    batch). Honest no-op if fewer than MIN_DISTRICTS_FOR_FIT districts qualify
    — GWR bandwidth selection isn't meaningful below that, and this never
    fabricates coefficients to fill the gap.
    """
    latest_year_subq = (
        select(SocioEconomicIndicator.district_id, func.max(SocioEconomicIndicator.year).label("year"))
        .group_by(SocioEconomicIndicator.district_id)
        .subquery()
    )
    indicator_rows = (
        await db.execute(
            select(SocioEconomicIndicator).join(
                latest_year_subq,
                (SocioEconomicIndicator.district_id == latest_year_subq.c.district_id)
                & (SocioEconomicIndicator.year == latest_year_subq.c.year),
            )
        )
    ).scalars().all()

    centroid_rows = (
        await db.execute(
            text(
                "SELECT district_id, AVG(latitude) AS lat, AVG(longitude) AS lon "
                "FROM case_master WHERE district_id IS NOT NULL AND latitude IS NOT NULL "
                "GROUP BY district_id"
            )
        )
    ).all()
    centroids = {row.district_id: (float(row.lat), float(row.lon)) for row in centroid_rows}

    observations: List[Dict[str, Any]] = []
    for indicator in indicator_rows:
        centroid = centroids.get(indicator.district_id)
        if not centroid or any(getattr(indicator, col) is None for col in _FACTOR_COLUMNS):
            continue

        # chi_weighted_count is nullable and, in this seed data, unpopulated
        # for every row (never backfilled by the seeder) — falling back to
        # the raw count per-row keeps the regression target non-degenerate
        # instead of silently summing to zero for every district. This is a
        # data-completeness fallback, not a fabricated distribution: it's the
        # same events, just unweighted by severity until CHI weights are
        # actually computed for this dataset.
        crime_total = (
            await db.execute(
                select(
                    func.coalesce(
                        func.sum(func.coalesce(CrimeStatAggregate.chi_weighted_count, CrimeStatAggregate.count)), 0.0
                    )
                ).where(
                    CrimeStatAggregate.district_id == indicator.district_id,
                    CrimeStatAggregate.year == indicator.year,
                )
            )
        ).scalar_one()

        observations.append({
            "district_id": indicator.district_id,
            "year": indicator.year,
            "coords": centroid,
            "x": [float(getattr(indicator, col)) for col in _FACTOR_COLUMNS],
            "y": float(crime_total or 0.0),
        })

    if len(observations) < MIN_DISTRICTS_FOR_FIT:
        log.warning("GWR skipped — insufficient districts with complete data", count=len(observations))
        return {"status": "skipped", "reason": "insufficient_data", "districts_available": len(observations)}

    from mgwr.gwr import GWR
    from mgwr.sel_bw import Sel_BW

    coords = [obs["coords"] for obs in observations]
    y = np.array([[obs["y"]] for obs in observations])
    x = np.array([obs["x"] for obs in observations])

    try:
        # Sel_BW's adaptive-kernel (KNN) bandwidth search defaults to a
        # candidate range that isn't clamped to the sample size — with a
        # small district count (Karnataka has 31), the unclamped default
        # tries k values past n and crashes on np.partition. bw_max=n is the
        # correct upper bound for an adaptive bandwidth (all neighbors);
        # bw_min is a floor a few past the parameter count (intercept + 3
        # factors here) so no local fit is run on a near-singular neighbor set.
        n_observations = len(observations)
        bw_min = min(x.shape[1] + 3, n_observations)
        bandwidth = Sel_BW(coords, y, x).search(bw_min=bw_min, bw_max=n_observations)
        results = GWR(coords, y, x, bandwidth).fit()
    except Exception as exc:
        log.error("GWR fit failed", error=str(exc))
        return {"status": "error", "reason": str(exc)}

    run_timestamp = datetime.now(timezone.utc)
    data_version = str(max(obs["year"] for obs in observations))
    written_district_ids: List[int] = []

    for i, obs in enumerate(observations):
        # results.params columns: [intercept, literacy, unemployment, urbanization]
        coefficients = {
            "intercept": _safe_float(float(results.params[i, 0])),
            **{col: _safe_float(float(results.params[i, j + 1])) for j, col in enumerate(_FACTOR_COLUMNS)},
        }
        local_r2 = _safe_float(float(results.localR2[i, 0])) if hasattr(results, "localR2") else None
        db.add(
            DistrictCompositeIndex(
                id=uuid.uuid4(),
                district_id=obs["district_id"],
                model_version=MODEL_VERSION,
                run_timestamp=run_timestamp,
                data_version=data_version,
                gwr_coefficients=coefficients,
                composite_score=local_r2,
            )
        )
        written_district_ids.append(obs["district_id"])

    await db.commit()
    log.info("GWR computed", districts=len(written_district_ids), bandwidth=bandwidth)
    return {
        "status": "ok",
        "districts_written": written_district_ids,
        "bandwidth": bandwidth,
        "model_version": MODEL_VERSION,
        "data_version": data_version,
    }
