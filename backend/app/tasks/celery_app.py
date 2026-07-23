"""
Celery application — background tasks for computationally heavy analytics.
Tasks: entity resolution batch, Hawkes fitting, risk re-scoring, GWR computation.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "karnataka_crime",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    # app.tasks.ingestion_tasks was referenced here but never actually existed
    # in the codebase — the worker crashed on every startup trying to import
    # it (ModuleNotFoundError), which is how this got caught. Document
    # ingestion currently runs synchronously via IngestionService, not as a
    # Celery task; add a real ingestion_tasks module here if that changes.
    include=[
        "app.tasks.analytics_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # GWR coefficients drift slowly (they're a function of district-year socio/
    # crime aggregates, which update at most monthly) — weekly is fresh enough
    # without re-fitting the spatial kernel needlessly. The admin "Recompute
    # GWR" action (POST /admin/jobs/recompute-gwr) triggers the same task
    # on demand for anyone who doesn't want to wait for the schedule.
    beat_schedule={
        "recompute-district-gwr-weekly": {
            "task": "tasks.recompute_district_stress_index",
            "schedule": crontab(hour=2, minute=0, day_of_week=1),
        },
        # Early-warning sweep (capability #8) — hourly is frequent enough to feel
        # proactive without hammering Neo4j; the detectors are idempotent so a
        # standing finding is never re-alerted. On Catalyst this becomes a Cron job.
        "early-warning-scan-hourly": {
            "task": "tasks.scan_early_warnings",
            "schedule": crontab(minute=0),
        },
    },
)
