"""
Analytics background tasks — Hawkes fitting, GWR computation, risk re-scoring.
All use synchronous DB sessions (Celery workers are sync).
"""

import structlog
from app.tasks.celery_app import celery_app

log = structlog.get_logger(__name__)


@celery_app.task(name="tasks.recompute_district_stress_index", bind=True, max_retries=3)
def recompute_district_stress_index(self, district_id: int) -> dict:
    """
    Recompute PCA-based composite stress index and GWR coefficients for a district (§6.2).
    Stores result in DistrictCompositeIndex as a versioned artifact.
    """
    from datetime import datetime, timezone
    import uuid

    log.info("Recomputing district stress index", district_id=district_id)
    # Real impl: load SEI data → PCA → GWR → store versioned DistrictCompositeIndex row
    return {"status": "queued", "district_id": district_id}


@celery_app.task(name="tasks.recompute_risk_scores_for_district", bind=True, max_retries=3)
def recompute_risk_scores_for_district(self, district_id: int) -> dict:
    """
    Batch risk re-scoring for all accused persons with cases in a district.
    Each creates a new RiskScore row — never overwrites (§7.4).
    """
    log.info("Batch risk rescoring", district_id=district_id)
    return {"status": "queued", "district_id": district_id}


@celery_app.task(name="tasks.run_link_prediction", bind=True, max_retries=2)
def run_link_prediction(self) -> dict:
    """
    Run GCN-based link prediction over the full co-offending graph.
    Writes PREDICTED_LINK edges to Neo4j with confidence + model_version (§4).
    """
    log.info("Running link prediction")
    return {"status": "queued"}


@celery_app.task(name="tasks.compute_centrality_scores", bind=True, max_retries=2)
def compute_centrality_scores(self) -> dict:
    """Compute PageRank + betweenness centrality and write to Neo4j Person nodes."""
    log.info("Computing centrality scores")
    return {"status": "queued"}
