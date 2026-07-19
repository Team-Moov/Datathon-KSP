"""
run_harness.py
===============
Runs the actual, unmodified scripts -- data/synthetic.py, load_data.py,
features/graph_features.py, and the mo_linkage/lead_rec/risk_score
train+infer pairs -- against a local SQLite file instead of Postgres.
Each script runs in its own subprocess with sqlite_shim installed first,
mirroring exactly how it would be invoked manually (`python3 script.py
--dsn ...`) except psycopg2.connect is redirected underneath.

Run from the repo root: python3 test_harness/run_harness.py
"""

import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HARNESS_DIR = os.path.join(REPO_ROOT, "test_harness")
SQLITE_PATH = os.path.join(HARNESS_DIR, "test.db")
SHIM_LAUNCHER = os.path.join(HARNESS_DIR, "_launch.py")


def run(script_relpath, args=None, cwd=None):
    args = args or []
    script_path = os.path.join(REPO_ROOT, script_relpath)
    cwd = cwd or os.path.dirname(script_path)
    cmd = [sys.executable, SHIM_LAUNCHER, SQLITE_PATH, script_path] + args
    print(f"\n{'='*70}\n>>> {script_relpath} {' '.join(args)}\n{'='*70}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"!!! FAILED: {script_relpath} (exit {result.returncode})")
        sys.exit(result.returncode)


def main():
    if os.path.exists(SQLITE_PATH):
        os.remove(SQLITE_PATH)

    print("Creating SQLite schema...")
    import sqlite3
    conn = sqlite3.connect(SQLITE_PATH)
    with open(os.path.join(HARNESS_DIR, "sqlite_schema.sql")) as f:
        conn.executescript(f.read())
    conn.close()
    print("Schema created.")

    # --- 1. Generate synthetic data (no DB involved at all) ---
    data_out = os.path.join(REPO_ROOT, "data", "output")
    run("data/synthetic.py", ["--out-dir", data_out])

    # --- 2. Load into SQLite via the real load_data.py, unmodified ---
    run("load_data.py", ["--data-dir", data_out], cwd=REPO_ROOT)

    # --- 3. Graph features ---
    run("features/graph_features.py")

    # --- 4. Severity history (standalone check) ---
    run("features/severity_history.py")

    # --- 5. MO linkage ---
    artifacts_mo = os.path.join(REPO_ROOT, "models", "mo_linkage", "artifacts")
    run("models/mo_linkage/train_siamese.py", ["--out-dir", artifacts_mo])
    run("models/mo_linkage/infer.py", ["--artifacts-dir", artifacts_mo])

    # --- 6. Lead recommendation ---
    artifacts_lr = os.path.join(REPO_ROOT, "models", "lead_rec", "artifacts")
    run("models/lead_rec/train_node2vec_logreg.py", ["--out-dir", artifacts_lr])
    run("models/lead_rec/infer.py", ["--artifacts-dir", artifacts_lr])

    # --- 7. Risk score ---
    artifacts_rs = os.path.join(REPO_ROOT, "models", "risk_score", "artifacts")
    run("models/risk_score/train_survival.py", ["--out-dir", artifacts_rs])
    run("models/risk_score/infer.py", ["--artifacts-dir", artifacts_rs])

    # --- verification ---
    print(f"\n{'='*70}\nVERIFICATION\n{'='*70}")
    conn = sqlite3.connect(SQLITE_PATH)
    for table in ["person", "incident", "offense", "case_person_role",
                   "mo_linkage_cluster", "person_graph_metric", "risk_score", "predicted_link"]:
        n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {n} rows")
    conn.close()
    print(f"\nSQLite DB at: {SQLITE_PATH}")
    print("All scripts ran unmodified via the shim -- this validates the actual ML logic,")
    print("not a simplified stand-in. Still needs real Postgres+pgvector verification later")
    print("for schema.sql itself and anything vector-search related.")


if __name__ == "__main__":
    main()