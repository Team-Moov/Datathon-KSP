"""
infer.py
========
Scores candidate person-pairs on the current full multiplex graph and
writes leads to predicted_link. Candidates are restricted to pairs with at
least one common neighbor and no existing direct edge -- a "lead" should
have some plausible connecting context, not be a random guess across the
whole population (with ~700 nodes, all-pairs would be ~250k mostly-
meaningless comparisons).

Evidence is derived from the actual connecting structure (shared
associates, and which edge types those shared ties are made of) so every
predicted link resolves to something an investigator can click into,
not just a bare confidence number.
"""

import argparse
import json
import os

import joblib
import numpy as np
import psycopg2
import psycopg2.extras

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "features"))  # ml/features/
from graph_utils import build_multiplex_graph


def generate_candidates(G, max_candidates=2000):
    candidates = []
    for node in G.nodes():
        neighbors = set(G.neighbors(node))
        two_hop = set()
        for nb in neighbors:
            two_hop |= set(G.neighbors(nb))
        two_hop -= neighbors
        two_hop.discard(node)
        for other in two_hop:
            if node < other:  # dedup unordered pairs
                candidates.append((node, other))
    if len(candidates) > max_candidates:
        import random
        random.seed(42)
        candidates = random.sample(candidates, max_candidates)
    return candidates


def build_evidence(G, u, v):
    common = set(G.neighbors(u)) & set(G.neighbors(v))
    if not common:
        return "indirect network proximity (no shared associate found post-filtering)"
    type_counts = {}
    for c in common:
        types_u = G[u][c].get("edge_types", {})
        types_v = G[v][c].get("edge_types", {})
        for t in set(types_u) | set(types_v):
            type_counts[t] = type_counts.get(t, 0) + 1
    type_summary = ", ".join(f"{k}:{v}" for k, v in sorted(type_counts.items()))
    return f"{len(common)} shared associate(s) via [{type_summary}]"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--artifacts-dir", default="./artifacts")
    ap.add_argument("--top-n", type=int, default=100)
    args = ap.parse_args()

    with open(os.path.join(args.artifacts_dir, "lead_rec_metadata.json")) as f:
        metadata = json.load(f)
    model_version = metadata["model_version"]
    clf = joblib.load(os.path.join(args.artifacts_dir, "logreg.joblib"))
    node_ids = np.load(os.path.join(args.artifacts_dir, "node_ids.npy"), allow_pickle=True)
    embeddings_arr = np.load(os.path.join(args.artifacts_dir, "embeddings.npy"))
    embeddings = {nid: embeddings_arr[i] for i, nid in enumerate(node_ids)}

    conn = psycopg2.connect(args.dsn)
    G = build_multiplex_graph(conn, as_of_date=None, include_mo_edges=True, include_financial_edges=True)
    print(f"Scoring on graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

    candidates = generate_candidates(G)
    candidates = [(u, v) for u, v in candidates if u in embeddings and v in embeddings]
    print(f"Candidate pairs (2-hop, not directly connected): {len(candidates)}")

    if not candidates:
        print("No candidates to score.")
        return

    X = np.stack([embeddings[u] * embeddings[v] for u, v in candidates])
    scores = clf.predict_proba(X)[:, 1]

    order = np.argsort(-scores)[: args.top_n]
    rows = []
    for i in order:
        u, v = candidates[i]
        evidence = build_evidence(G, u, v)
        rows.append((u, v, float(scores[i]), "node2vec_logreg_v1", evidence, model_version))

    cur = conn.cursor()
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO predicted_link (person_id_a, person_id_b, confidence, source_tool, evidence, model_version)
           VALUES %s""",
        rows,
    )
    conn.commit()
    print(f"Wrote {len(rows)} predicted links (top {args.top_n} by confidence)")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
