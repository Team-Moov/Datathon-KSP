"""
fairness_audit.py
==================
Subgroup error-rate / calibration audit for risk_score. No protected
attributes (religion/caste) were ever modeled as features in this build --
but that alone doesn't guarantee fairness. Centrality turned out to be the
dominant feature in the trained model (see risk_score_metadata.json's
permutation importance), and network position can carry geography-based
proxy signal even with no protected field anywhere in the pipeline. This
audit checks for that specifically, using district as the subgroup
variable -- the only demographic-adjacent field this build carries at all.

THREE SEPARATE CHECKS, reported separately on purpose:
  1. Per-district concordance -- does the model discriminate risk equally
     well within every district, or well in some and poorly in others?
     (a "separation"-style check)
  2. Per-district calibration -- does mean predicted risk track actual
     observed event rate consistently, or does the model systematically
     over/under-predict for specific districts? (a "calibration"-style
     check)
  3. Direct proxy check -- does centrality (the dominant feature) or the
     final risk score correlate with district-level socio-economic
     indicators? If so, risk scores are partly tracking which district
     someone is in via network structure, not just their own behavior --
     worth knowing explicitly before calling this "validated," per the
     COMPAS lesson this design was built to avoid repeating.

Per that same COMPAS lesson: equal error rates (separation) and equal
predictive accuracy given a score (calibration) are different, sometimes
mutually exclusive properties. This script reports both rather than
picking one and declaring the model fair.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import psycopg2
from scipy.stats import pearsonr

sys.path.append(str(Path(__file__).resolve().parents[1] / "features"))  # eval/ -> root/features/
sys.path.append(str(Path(__file__).resolve().parents[1] / "models" / "risk_score"))  # reuse build_dataset, don't duplicate it

from train_survival import build_dataset  # noqa: E402


def load_person_districts(conn):
    cur = conn.cursor()
    cur.execute("SELECT person_id, district_id FROM person")
    result = dict(cur.fetchall())
    cur.close()
    return result


def load_district_socioeconomic(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT ON (district_id) district_id, composite_stress_index
        FROM district_socioeconomic ORDER BY district_id, year DESC
    """)
    result = {r[0]: float(r[1]) for r in cur.fetchall()}
    cur.close()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    default_model_path = str(Path(__file__).resolve().parents[1] / "models" / "risk_score" / "artifacts" / "risk_survival_model.joblib")
    ap.add_argument("--model-path", default=default_model_path)
    ap.add_argument("--min-subgroup-size", type=int, default=10,
                     help="districts with fewer persons than this are reported but flagged low-confidence")
    ap.add_argument("--out-dir", default="./artifacts")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    conn = psycopg2.connect(args.dsn)
    records = build_dataset(conn)  # same function train_survival.py uses -- one source of truth
    districts = load_person_districts(conn)
    district_ses = load_district_socioeconomic(conn)

    rsf = joblib.load(args.model_path)
    feature_cols = ["severity_history", "centrality", "mo_consistency", "associate_risk"]

    for r in records:
        r["district_id"] = districts.get(r["person_id"], "unknown")

    X_all = np.array([[r[c] for c in feature_cols] for r in records], dtype=float)
    all_scores = rsf.predict(X_all)
    for r, s in zip(records, all_scores):
        r["risk_score"] = float(s)

    # --- group by district ---
    by_district = {}
    for r in records:
        by_district.setdefault(r["district_id"], []).append(r)

    from sksurv.metrics import concordance_index_censored

    overall_c = concordance_index_censored(
        np.array([r["event"] for r in records]),
        np.array([r["time_days"] for r in records]),
        np.array([r["risk_score"] for r in records]),
    )[0]

    subgroup_report = []
    for district_id, recs in sorted(by_district.items()):
        n = len(recs)
        events = np.array([r["event"] for r in recs])
        times = np.array([r["time_days"] for r in recs])
        scores = np.array([r["risk_score"] for r in recs])
        mean_risk = float(scores.mean())
        observed_event_rate = float(events.mean())
        mean_centrality = float(np.mean([r["centrality"] for r in recs]))

        # concordance is undefined / unstable with too few comparable pairs or no events
        try:
            if n >= args.min_subgroup_size and events.sum() >= 2:
                c_index = concordance_index_censored(events, times, scores)[0]
            else:
                c_index = None
        except Exception:
            c_index = None

        subgroup_report.append({
            "district_id": district_id,
            "n_persons": n,
            "low_confidence": n < args.min_subgroup_size,
            "concordance_index": c_index,
            "concordance_gap_vs_overall": (c_index - overall_c) if c_index is not None else None,
            "mean_predicted_risk": mean_risk,
            "observed_event_rate": observed_event_rate,
            "mean_centrality": mean_centrality,
        })

    # --- flag districts where concordance is notably worse than overall (separation check) ---
    flagged_separation = [
        d for d in subgroup_report
        if d["concordance_index"] is not None and d["concordance_gap_vs_overall"] < -0.10
    ]

    # --- calibration check: does mean_predicted_risk rank districts the
    # same way observed_event_rate does? Spearman-style check via simple
    # rank comparison, since we only have ~31 district-level points ---
    valid = [d for d in subgroup_report if not d["low_confidence"]]
    risk_ranks = {d["district_id"]: i for i, d in enumerate(
        sorted(valid, key=lambda d: d["mean_predicted_risk"]))}
    outcome_ranks = {d["district_id"]: i for i, d in enumerate(
        sorted(valid, key=lambda d: d["observed_event_rate"]))}
    rank_gaps = [
        (d["district_id"], abs(risk_ranks[d["district_id"]] - outcome_ranks[d["district_id"]]))
        for d in valid
    ]
    rank_gaps.sort(key=lambda x: -x[1])
    worst_calibration_gaps = rank_gaps[:5]

    # --- direct proxy check: does mean centrality per district correlate
    # with district-level socio-economic composite index? ---
    paired = [
        (district_ses[d["district_id"]], d["mean_centrality"])
        for d in subgroup_report
        if d["district_id"] in district_ses and not d["low_confidence"]
    ]
    proxy_correlation = None
    if len(paired) >= 5:
        ses_vals, cent_vals = zip(*paired)
        r_value, p_value = pearsonr(ses_vals, cent_vals)
        proxy_correlation = {"pearson_r": float(r_value), "p_value": float(p_value), "n_districts": len(paired)}

    risk_ses_paired = [
        (district_ses[d["district_id"]], d["mean_predicted_risk"])
        for d in subgroup_report
        if d["district_id"] in district_ses and not d["low_confidence"]
    ]
    risk_proxy_correlation = None
    if len(risk_ses_paired) >= 5:
        ses_vals, risk_vals = zip(*risk_ses_paired)
        r_value, p_value = pearsonr(ses_vals, risk_vals)
        risk_proxy_correlation = {"pearson_r": float(r_value), "p_value": float(p_value), "n_districts": len(risk_ses_paired)}

    report = {
        "overall_concordance_index": float(overall_c),
        "n_districts": len(subgroup_report),
        "n_districts_flagged_low_confidence": sum(1 for d in subgroup_report if d["low_confidence"]),
        "districts_with_concordance_gap_below_-0.10": flagged_separation,
        "worst_calibration_rank_gaps_top5": worst_calibration_gaps,
        "centrality_vs_district_socioeconomic_correlation": proxy_correlation,
        "risk_score_vs_district_socioeconomic_correlation": risk_proxy_correlation,
        "per_district_detail": subgroup_report,
    }

    with open(os.path.join(args.out_dir, "fairness_audit_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"Overall concordance index: {overall_c:.3f}")
    print(f"Districts audited: {len(subgroup_report)} "
          f"({report['n_districts_flagged_low_confidence']} flagged low-confidence, n<{args.min_subgroup_size})")
    print(f"\nSeparation check -- districts with concordance >0.10 below overall: {len(flagged_separation)}")
    for d in flagged_separation:
        print(f"  {d['district_id']}: c-index={d['concordance_index']:.3f} (n={d['n_persons']})")

    print("\nCalibration check -- top rank mismatches (predicted risk rank vs actual event-rate rank):")
    for district_id, gap in worst_calibration_gaps:
        print(f"  {district_id}: rank gap = {gap}")

    print("\nProxy check -- mean centrality vs district socio-economic composite index:")
    if proxy_correlation:
        print(f"  Pearson r = {proxy_correlation['pearson_r']:.3f}  (p = {proxy_correlation['p_value']:.3f}, "
              f"n = {proxy_correlation['n_districts']} districts)")
    print("Proxy check -- mean risk_score vs district socio-economic composite index:")
    if risk_proxy_correlation:
        print(f"  Pearson r = {risk_proxy_correlation['pearson_r']:.3f}  (p = {risk_proxy_correlation['p_value']:.3f}, "
              f"n = {risk_proxy_correlation['n_districts']} districts)")

    print(f"\nFull report written to {os.path.join(args.out_dir, 'fairness_audit_report.json')}")
    conn.close()


if __name__ == "__main__":
    main()
