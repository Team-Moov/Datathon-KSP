"""
Compute and store GWR coefficients for every qualifying district (§6.2).

Idempotent to re-run: each run is a new versioned row set (never overwrites a
prior run), consistent with how risk_score/mo_linkage_cluster are versioned
elsewhere in this codebase.

Normal path is now automatic (weekly Celery beat schedule, see
app/tasks/celery_app.py) or the admin-triggered "Recompute GWR" action
(System Jobs page / POST /admin/jobs/recompute-gwr), both of which run
app.tasks.analytics_tasks.recompute_district_stress_index — the same
compute_all_districts_gwr call this script makes. This script exists only for
an out-of-band run without API/Celery access.

Run:  docker compose exec api python -m scripts.compute_district_gwr
"""

import asyncio
import json

from app.core.database import AdminSessionFactory
from app.services.analytics.gwr import compute_all_districts_gwr


async def run() -> None:
    async with AdminSessionFactory() as session:
        result = await compute_all_districts_gwr(session)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(run())
