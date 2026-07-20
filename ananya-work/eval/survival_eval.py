"""
survival_eval.py
=================
Evaluation logic for the risk-score survival model, pulled out of
train_survival.py so it's a single source of truth -- both the training
script and anyone re-evaluating a saved model later (e.g. after a data
refresh, without retraining) call the same functions instead of two
copies of the same concordance-index logic silently drifting apart.
"""

import numpy as np
from sksurv.metrics import concordance_index_censored


def evaluate_concordance(y_event: np.ndarray, y_time: np.ndarray, risk_scores: np.ndarray) -> float:
    """Concordance index: fraction of comparable pairs correctly ordered by
    risk, properly accounting for censored observations (unlike plain
    accuracy, which can't handle 'we don't know yet' outcomes)."""
    return concordance_index_censored(y_event, y_time, risk_scores)[0]


def evaluate_against_baseline(y_event: np.ndarray, y_time: np.ndarray,
                                model_scores: np.ndarray, baseline_scores: np.ndarray) -> dict:
    """Compares a trained model's concordance against a single-feature
    baseline -- the question this answers is 'does the model add anything
    over the single most obvious feature,' not just 'is the model better
    than random.'"""
    model_c = evaluate_concordance(y_event, y_time, model_scores)
    baseline_c = evaluate_concordance(y_event, y_time, baseline_scores)
    return {
        "model_concordance": float(model_c),
        "baseline_concordance": float(baseline_c),
        "improvement_over_baseline": float(model_c - baseline_c),
    }


def evaluate_by_subgroup(records: list[dict], scores: np.ndarray, subgroup_key: str,
                          min_subgroup_size: int = 10) -> list[dict]:
    """Per-subgroup concordance -- the same building block fairness_audit.py
    uses for its separation check, exposed here so it isn't duplicated a
    third time if another script needs a subgroup breakdown later."""
    by_group = {}
    for r, s in zip(records, scores):
        by_group.setdefault(r[subgroup_key], []).append((r["event"], r["time_days"], s))

    report = []
    for group_val, items in sorted(by_group.items()):
        n = len(items)
        events = np.array([i[0] for i in items])
        times = np.array([i[1] for i in items])
        group_scores = np.array([i[2] for i in items])
        c_index = None
        if n >= min_subgroup_size and events.sum() >= 2:
            try:
                c_index = evaluate_concordance(events, times, group_scores)
            except Exception:
                c_index = None
        report.append({
            subgroup_key: group_val, "n": n,
            "low_confidence": n < min_subgroup_size,
            "concordance_index": c_index,
        })
    return report