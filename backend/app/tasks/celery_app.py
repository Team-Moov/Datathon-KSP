"""
Celery application — background tasks for computationally heavy analytics.
Tasks: entity resolution batch, Hawkes fitting, risk re-scoring, GWR computation.
"""

from celery import Celery

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
)
