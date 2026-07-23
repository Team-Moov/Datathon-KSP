"""
Analytics background tasks — Hawkes fitting, GWR computation, risk re-scoring.
All use synchronous DB sessions (Celery workers are sync).

GAP-01 fix: All four tasks now have real bodies. Previously they all returned
{"status": "queued"} stubs, meaning the Celery beat schedule fired but nothing
actually ran.

Integration strategy for Ananya's ML artifacts:
  - compute_centrality_scores: builds the co-offending graph from Postgres
    (case_master / person_case_role) using the same NetworkX logic Ananya used
    (graph_features.py), then writes results to Neo4j Person node properties so
    risk_profiling._get_network_centrality() can read them.

  - run_link_prediction: loads the trained node2vec + logreg artifacts from
    ananya-work/models/lead_rec/artifacts/ and calls
    GraphSyncService.upsert_predicted_link() for each top-N result so the
    network_analysis.get_link_predictions() endpoint can serve them.

  - recompute_risk_scores_for_district: batch-rescores all accused persons in a
    district by running RiskProfilingService through an asyncio event loop.

  - recompute_district_stress_index: replicates the composite_index.py logic
    (percentile-rank across NDAP SEI indicators) and writes a versioned
    DistrictCompositeIndex row.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog
from app.tasks.celery_app import celery_app

log = structlog.get_logger(__name__)


# ── Helper: run async code from a sync Celery worker ─────────────────────────

def _run_async(coro):
    """Execute an async coroutine from a sync Celery task."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Task 1: Centrality scores ─────────────────────────────────────────────────

@celery_app.task(name="tasks.compute_centrality_scores", bind=True, max_retries=2)
def compute_centrality_scores(self) -> dict:
    """
    Disabled in favor of Ananya's ML sync pipeline which writes these properties.
    """
    log.info("compute_centrality_scores disabled; relying on ML sync script.")
    return {"status": "skipped", "reason": "disabled"}





# ── Task 2: Link prediction ───────────────────────────────────────────────────

@celery_app.task(name="tasks.run_link_prediction", bind=True, max_retries=2)
def run_link_prediction(self, top_n: int = 100) -> dict:
    """
    Disabled in favor of Ananya's ML sync pipeline which writes these properties.
    """
    log.info("run_link_prediction disabled; relying on ML sync script.")
    return {"status": "skipped", "reason": "disabled"}





# ── Task 3: Batch risk rescoring ─────────────────────────────────────────────

@celery_app.task(name="tasks.recompute_risk_scores_for_district", bind=True, max_retries=3)
def recompute_risk_scores_for_district(self, district_id: int) -> dict:
    """
    Disabled in favor of Ananya's ML sync pipeline which syncs all scores.
    """
    log.info("recompute_risk_scores_for_district disabled; relying on ML sync script.")
    return {"status": "skipped", "reason": "disabled"}





# ── Task 4: District GWR / composite index ────────────────────────────────────

@celery_app.task(name="tasks.recompute_district_stress_index", bind=True, max_retries=3)
def recompute_district_stress_index(self) -> dict:
    """
    Recompute GWR coefficients (socio factors → CHI-weighted crime harm) across
    all districts (§6.2), writing versioned DistrictCompositeIndex rows via
    app.services.analytics.gwr.compute_all_districts_gwr.

    Not per-district: GWR is fit once over every qualifying district (each
    district's local coefficient depends on every other district's
    observation via the spatial kernel), unlike the other three tasks in this
    module, so this task takes no district_id argument.

    Previously this task's body referenced DistrictCompositeIndex fields
    (year, method, composite_value) that don't exist on the model — it would
    have raised a TypeError on every run, meaning the GWR gap this closes was
    never actually being filled by this task despite it being scheduled.
    """
    try:
        return _run_async(_do_recompute_district_gwr())
    except Exception as exc:
        log.error("recompute_district_stress_index failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _do_recompute_district_gwr() -> dict:
    # AdminSessionFactory, not the RLS-restricted AsyncSessionFactory — this is
    # an internal batch job writing derived aggregate data across every
    # district, not a request scoped to one user (same reasoning as
    # scripts/embed_cases.py and scripts/compute_district_gwr.py).
    from app.core.database import AdminSessionFactory
    from app.services.analytics.gwr import compute_all_districts_gwr

    async with AdminSessionFactory() as db:
        return await compute_all_districts_gwr(db)


# ── Task 6: Early-warning scan ────────────────────────────────────────────────

@celery_app.task(name="tasks.scan_early_warnings", bind=True, max_retries=2)
def scan_early_warnings(self) -> dict:
    """
    Run the early-warning detectors (multi-jurisdiction repeat offenders +
    organized-group communities) and persist any newly-detected alerts
    (capability #8). Idempotent — signatures already present are skipped, so the
    hourly beat tick never duplicates a standing finding. This is the scheduled
    twin of POST /alerts/scan. Maps cleanly onto a Catalyst Cron trigger when the
    backend moves to AppSail.
    """
    try:
        return _run_async(_do_scan_early_warnings())
    except Exception as exc:
        log.error("scan_early_warnings failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


async def _do_scan_early_warnings() -> dict:
    # AdminSessionFactory: a system-wide detection sweep, not a user-scoped
    # request (same reasoning as the GWR/embedding batch jobs above).
    from app.core.database import AdminSessionFactory
    from app.services.analytics.early_warning import EarlyWarningService

    async with AdminSessionFactory() as db:
        result = await EarlyWarningService(db).scan()
        await db.commit()
        return result


# ── Task 5: Case-narrative embedding backfill ─────────────────────────────────

@celery_app.task(name="tasks.backfill_case_embeddings", bind=True, max_retries=1)
def backfill_case_embeddings(self) -> dict:
    """
    Embed any CaseMaster.brief_facts rows that predate the embed-on-ingest
    path or an embedding-model swap (§8.1 vector RAG). Idempotent — safe to
    trigger repeatedly, only embeds rows still missing a vector_chunk.

    Triggered on demand from the System Jobs admin page
    (POST /admin/jobs/backfill-embeddings) rather than requiring shell/CLI
    access — see EmbeddingService.backfill_case_embeddings for the shared
    implementation (also used by scripts/embed_cases.py as an out-of-band
    fallback).
    """
    from app.services.embedding_service import EmbeddingService

    try:
        return _run_async(EmbeddingService.backfill_case_embeddings())
    except Exception as exc:
        log.error("backfill_case_embeddings failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)
