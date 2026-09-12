"""
Internal task-trigger endpoints for Cloud Scheduler, which replaces Celery
Beat on Cloud Run (Beat is a long-lived scheduler process; Cloud Run only
runs containers in response to a request/invocation, so there's nothing for
Beat to run inside). Cloud Scheduler hits these on the same cron schedule
Beat used to (see the now-removed entries in app/tasks/celery_app.py's
beat_schedule) and they just enqueue the same Celery tasks.

Auth is a shared secret (X-Internal-Task-Secret, checked against
settings.INTERNAL_TASK_SECRET) rather than the normal user JWT flow — Cloud
Scheduler isn't a logged-in user and has no case-data access of its own to
authorize; it only ever triggers these two already-idempotent, already
existing tasks (the same ones POST /admin/jobs/recompute-gwr already exposes
to authenticated admins). Demo/pilot-grade tradeoff, same class as
ALLOW_MOCK_MFA — acceptable because these routes can't read or write case
data themselves, only enqueue a task that runs under its own authorization.
"""

from fastapi import APIRouter, Header, HTTPException, status

from app.core.config import settings

router = APIRouter()


def _verify_internal_task_secret(x_internal_task_secret: str = Header(...)) -> None:
    if x_internal_task_secret != settings.INTERNAL_TASK_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal task secret")


@router.post("/recompute-gwr", status_code=status.HTTP_202_ACCEPTED)
async def trigger_recompute_gwr(x_internal_task_secret: str = Header(...)) -> dict:
    _verify_internal_task_secret(x_internal_task_secret)

    from app.tasks.analytics_tasks import recompute_district_stress_index

    async_result = recompute_district_stress_index.delay()
    return {"task_id": async_result.id, "task_name": "tasks.recompute_district_stress_index"}


@router.post("/scan-early-warnings", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scan_early_warnings(x_internal_task_secret: str = Header(...)) -> dict:
    _verify_internal_task_secret(x_internal_task_secret)

    from app.tasks.analytics_tasks import scan_early_warnings

    async_result = scan_early_warnings.delay()
    return {"task_id": async_result.id, "task_name": "tasks.scan_early_warnings"}
