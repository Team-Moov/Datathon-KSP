"""
ML Model Registry — the transparency backbone for capability #9 (Explainable AI &
Transparent Analytics) and #5 (offender profiling accountability).

Every ML model in this platform is trained offline in `ananya-work/` and its
outputs are synced into the poly-store (risk scores, predicted links, MO clusters).
Until now the *quality* of those models — their held-out metrics, feature
importances, and fairness posture — lived only in the training-time metadata JSON
files and never reached the product. This registry is the single source of truth
that surfaces them.

Values below are transcribed from the trained-model metadata
(`ananya-work/models/*/metadata.json`, read at build time). `load_live_overrides()`
best-effort refreshes them from those files if the ML tree is mounted at runtime
(local dev), so a retrain is reflected without a code edit; in the deployed backend
image, where `ananya-work/` isn't present, the transcribed values stand on their own.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)


# ── Source-of-truth model cards (transcribed from trained metadata) ───────────
_MODEL_CARDS: Dict[str, Dict[str, Any]] = {
    "risk_survival_rsf_v1": {
        "model_version": "risk_survival_rsf_v1",
        "name": "Offender Risk (survival)",
        "family": "Random Survival Forest",
        "task": "Time-to-reoffense risk scoring (§7)",
        "capability": "Criminology-Based Offender Profiling",
        "primary_metric": {"label": "Held-out concordance index", "value": 0.7117},
        "metrics": {
            "held_out_concordance_index": 0.7117,
            "baseline_severity_only_concordance": 0.4964,
            "improvement_over_baseline": 0.2153,
        },
        "feature_importance": {
            "severity_history": 0.0193,
            "centrality": 0.1461,
            "mo_consistency": 0.0086,
            "associate_risk": 0.0632,
        },
        "feature_importance_method": "permutation",
        "training": {"n_persons": 606, "n_observed_events": 417, "n_censored": 189},
        "fairness": {
            "protected_attributes_used": False,
            "protected_attributes": ["ReligionID", "CasteID"],
            "audit": (
                "Subgroup audit by district (per-district concordance, calibration, and a direct "
                "proxy check on centrality — the dominant feature). Centrality can carry geography-based "
                "proxy signal even with no protected field modeled, so this is checked explicitly per the "
                "COMPAS lesson. Score prioritizes investigative attention only; human sign-off required."
            ),
        },
    },
    "node2vec_logreg_v1": {
        "model_version": "node2vec_logreg_v1",
        "name": "Link Prediction (leads)",
        "family": "node2vec embeddings + logistic regression",
        "task": "Plausible-but-unconfirmed relationship prediction (§4)",
        "capability": "Criminal Network & Relationship Analysis",
        "primary_metric": {"label": "Temporal-holdout AUC", "value": 0.7663},
        "metrics": {
            "holdout_auc": 0.7663,
            "holdout_precision_at_k": 0.8,
            "holdout_k": 20,
            "holdout_cutoff_date": "2025-06-24",
            "n_new_edges_in_holdout": 26,
        },
        "feature_importance": None,
        "training": {"final_graph_nodes": 673, "final_graph_edges": 38170},
        "fairness": {
            "protected_attributes_used": False,
            "protected_attributes": ["ReligionID", "CasteID"],
            "audit": (
                "Predictions are surfaced as leads with a confidence score, never rendered identically "
                "to a confirmed edge. Evaluated on a temporal holdout — trained on the graph as it looked "
                "at the cutoff, scored on edges that actually formed afterward."
            ),
        },
    },
    "mo_linkage_tfidf_contrastive_v1": {
        "model_version": "mo_linkage_tfidf_contrastive_v1",
        "name": "MO Linkage (series detection)",
        "family": "TF-IDF + contrastive Siamese projection",
        "task": "Behavioral crime-series linkage by modus operandi (§5)",
        "capability": "Crime Pattern & Behavioral Profiling",
        "primary_metric": {"label": "Recall@3", "value": 0.8966},
        "metrics": {
            "trained_recall_at_1": 0.5632,
            "trained_recall_at_3": 0.8966,
            "baseline_recall_at_3": 0.7931,
            "cluster_threshold_ari": 0.6088,
            "cluster_distance_threshold": 0.06,
        },
        "feature_importance": None,
        "training": {"n_train_pairs": 1072, "n_series_total": 130},
        "fairness": {
            "protected_attributes_used": False,
            "protected_attributes": ["ReligionID", "CasteID"],
            "audit": (
                "Operates on MO free-text only (weapon, entry method, target, time-of-day patterns) — "
                "no demographic input. Suggests a probable series for human review; never an arrest basis."
            ),
        },
    },
}

# Where the live metadata files live, relative to the repo root (…/backend/app/services/ml_registry.py → repo root is parents[3]).
_ML_METADATA_PATHS = {
    "risk_survival_rsf_v1": "ananya-work/models/risk_score/risk_score_metadata.json",
    "node2vec_logreg_v1": "ananya-work/models/lead_rec/lead_rec_metadata.json",
    "mo_linkage_tfidf_contrastive_v1": "ananya-work/models/mo_linkage/metadata.json",
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_live_overrides() -> None:
    """Best-effort refresh of metric fields from the on-disk training metadata, if
    the ML tree is mounted (local dev). Never raises — a missing file just means the
    transcribed values stand."""
    root = _repo_root()
    for version, rel_path in _ML_METADATA_PATHS.items():
        path = root / rel_path
        try:
            if not path.exists():
                continue
            with path.open(encoding="utf-8-sig") as handle:
                live = json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive
            log.debug("ml_registry override skipped", version=version, error=str(exc))
            continue
        card = _MODEL_CARDS.get(version)
        if not card:
            continue
        if "feature_importance" in live and live["feature_importance"]:
            card["feature_importance"] = live["feature_importance"]
        # Merge any recognized metric keys straight through.
        for key in ("held_out_concordance_index", "holdout_auc", "trained_recall_at_k"):
            if key in live:
                card["metrics"][key] = live[key]


@lru_cache(maxsize=1)
def _initialized_cards() -> Dict[str, Dict[str, Any]]:
    load_live_overrides()
    return _MODEL_CARDS


def get_model_cards() -> List[Dict[str, Any]]:
    """All model cards, for the transparency / model-registry surface."""
    return list(_initialized_cards().values())


def get_model_card(model_version: str) -> Optional[Dict[str, Any]]:
    """One card by version — used to enrich a risk-score response with the model's
    quality metrics and feature importances at the point it's shown."""
    return _initialized_cards().get(model_version)
