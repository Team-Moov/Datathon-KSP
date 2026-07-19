"""
infer.py
========
Loads the trained survival model and scores every person in the dataset,
writing to risk_score (append-only -- a new run adds new rows, never
overwrites a prior score, so an investigator can see a person's risk
trend over time).

Split out from train_survival.py to match the train/infer pattern used by
mo_linkage and lead_rec -- training and scoring are different operations
with different cadences (retrain occasionally, rescore whenever new
incidents land).
"""

import argparse
import json
import os
import sys
from pathlib import Path

import joblib
import numpy as np
import psycopg2
import psycopg2.extras

sys.path.append(str(Path(__file__).resolve().parent))
from train_survival import build_dataset  # same dataset construction used at training time


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--artifacts-dir", default="./artifacts")
    args = ap.parse_args()

    with open(os.path.join(args.artifacts_dir, "risk_score_metadata.json")) as f:
        metadata = json.load(f)
    model_version = metadata["model_version"]
    feature_cols = metadata["feature_cols"]
    rsf = joblib.load(os.path.join(args.artifacts_dir, "risk_survival_model.joblib"))

    conn = psycopg2.connect(args.dsn)
    records = build_dataset(conn)
    print(f"Scoring {len(records)} persons with model_version={model_version}")

    X_all = np.array([[r[c] for c in feature_cols] for r in records], dtype=float)
    all_scores = rsf.predict(X_all)

    cur = conn.cursor()
    rows = [
        (r["person_id"], model_version, float(score),
         r["severity_history"], r["centrality"], r["mo_consistency"], r["associate_risk"])
        for r, score in zip(records, all_scores)
    ]
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO risk_score
           (person_id, model_version, score, severity_history_component,
            centrality_component, mo_consistency_component, associate_risk_component)
           VALUES %s""",
        rows,
    )
    conn.commit()
    print(f"Wrote {len(rows)} rows to risk_score")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()