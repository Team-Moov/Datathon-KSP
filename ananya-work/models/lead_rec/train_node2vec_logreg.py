"""
train_node2vec_logreg.py
=========================
Trains the "middle ground" lead-recommendation model: node2vec embeddings
(unsupervised, no labels needed) + logistic regression on the Hadamard
product of two persons' embeddings, predicting edge likelihood.

VALIDATION METHODOLOGY (the important part):
  We don't have conviction data or any sensitive ground-truth label for
  "these two people should be linked." What we DO have is the graph's own
  temporal structure. So:
    1. Pick a cutoff date ~6 months before the end of the data window.
    2. Build the graph as it looked AS OF that cutoff (co-offending +
       financial edges only -- see graph_utils.py's leakage note on why
       MO-similarity edges are excluded from this historical view).
    3. Train node2vec on that PAST graph only.
    4. Train logistic regression on the past graph's OWN edges (existing
       ties) vs. sampled non-edges.
    5. Test: score pairs of people who were both present in the past graph
       but NOT connected then. Check whether the pairs that scored highest
       are the ones that actually became edges by the end of the full data
       window. This is a genuinely causal test -- the model never saw
       anything past the cutoff during training.
  This whole methodology is what turns "no data to validate a link
  predictor against" into a non-issue: the graph's own edge-formation
  history over time IS the label.

  A separate, final model is then trained on the FULL current multiplex
  graph (including MO-similarity edges this time) for actual deployment --
  that final model is not what the reported metrics below describe.
"""

import argparse
import json
import os
import random

import joblib
import numpy as np
import psycopg2
from node2vec import Node2Vec
from sklearn.linear_model import LogisticRegression

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[2] / "features"))
sys.path.append(str(Path(__file__).resolve().parents[2] / "eval"))
from graph_utils import build_multiplex_graph
from link_pred_holdout import get_date_range, compute_cutoff, find_new_edges, sample_non_edges, evaluate_holdout

SEED = 42
random.seed(SEED)
np.random.seed(SEED)


def train_node2vec(G, dimensions=64, walk_length=20, num_walks=50, workers=2):
    if G.number_of_edges() == 0:
        raise ValueError("Graph has no edges -- can't train node2vec on an empty graph")
    n2v = Node2Vec(G, dimensions=dimensions, walk_length=walk_length, num_walks=num_walks,
                    workers=workers, weight_key="weight", quiet=True, seed=SEED)
    model = n2v.fit(window=5, min_count=1, seed=SEED)
    return {node: model.wv[str(node)] for node in G.nodes()}


def build_pair_features(embeddings, pairs):
    return np.stack([embeddings[a] * embeddings[b] for a, b in pairs])  # Hadamard product


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--holdout-days", type=int, default=180)
    ap.add_argument("--out-dir", default="./artifacts")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    conn = psycopg2.connect(args.dsn)
    lo, hi = get_date_range(conn)
    cutoff = compute_cutoff(conn, holdout_days=args.holdout_days)
    print(f"Data spans {lo} to {hi}. Holdout cutoff: {cutoff} ({args.holdout_days} days before end)")

    # --- past graph (training) and full graph (defines what "actually happened") ---
    past_G = build_multiplex_graph(conn, as_of_date=cutoff, include_mo_edges=False, include_financial_edges=True)
    full_G = build_multiplex_graph(conn, as_of_date=None, include_mo_edges=False, include_financial_edges=True)
    print(f"Past graph:  {past_G.number_of_nodes()} nodes, {past_G.number_of_edges()} edges")
    print(f"Full graph:  {full_G.number_of_nodes()} nodes, {full_G.number_of_edges()} edges")

    past_nodes = set(past_G.nodes())

    # --- new edges: connected in full graph, both endpoints existed in past graph, NOT connected in past graph ---
    new_edges = find_new_edges(past_G, full_G)
    print(f"New edges formed after cutoff (both endpoints pre-existing): {len(new_edges)}")

    if len(new_edges) < 5:
        print("Too few new edges to evaluate meaningfully -- try a longer holdout window.")

    # --- train node2vec on PAST graph only ---
    print("Training node2vec on past graph...")
    past_embeddings = train_node2vec(past_G)

    # --- train logistic regression on the past graph's own edges vs. sampled non-edges ---
    train_pos_pairs = list(past_G.edges())
    train_neg_pairs = sample_non_edges(past_G, past_nodes, n=len(train_pos_pairs))
    X_train = np.concatenate([
        build_pair_features(past_embeddings, train_pos_pairs),
        build_pair_features(past_embeddings, train_neg_pairs),
    ])
    y_train = np.array([1] * len(train_pos_pairs) + [0] * len(train_neg_pairs))
    clf = LogisticRegression(max_iter=1000)
    clf.fit(X_train, y_train)
    print(f"Trained logistic regression on {len(train_pos_pairs)} pos / {len(train_neg_pairs)} neg past-graph pairs")

    # --- evaluate on the true holdout: new edges vs. true non-edges (as of full graph) ---
    existing_or_new = set(tuple(sorted(e)) for e in full_G.edges())
    test_neg_pairs = sample_non_edges(full_G, past_nodes, n=len(new_edges) * 5, exclude_pairs=existing_or_new)
    holdout_result = evaluate_holdout(clf, past_embeddings, new_edges, test_neg_pairs)
    auc = holdout_result["auc_roc"]
    precision_at_k = holdout_result["precision_at_k"]
    k = holdout_result["k"]

    print("\nHOLDOUT RESULTS (never seen during training):")
    print(f"  AUC-ROC:        {auc:.3f}")
    print(f"  Precision@{k}:    {precision_at_k:.3f}  (chance level ~= {holdout_result['chance_level']:.3f})")

    # --- final deployable model: retrain on the FULL current multiplex graph, including MO edges ---
    print("\nRetraining final model on full current multiplex graph (incl. MO-similarity edges)...")
    final_G = build_multiplex_graph(conn, as_of_date=None, include_mo_edges=True, include_financial_edges=True)
    print(f"Final graph: {final_G.number_of_nodes()} nodes, {final_G.number_of_edges()} edges")
    final_embeddings = train_node2vec(final_G)
    final_pos_pairs = list(final_G.edges())
    final_neg_pairs = sample_non_edges(final_G, final_G.nodes(), n=len(final_pos_pairs))
    X_final = np.concatenate([
        build_pair_features(final_embeddings, final_pos_pairs),
        build_pair_features(final_embeddings, final_neg_pairs),
    ])
    y_final = np.array([1] * len(final_pos_pairs) + [0] * len(final_neg_pairs))
    final_clf = LogisticRegression(max_iter=1000)
    final_clf.fit(X_final, y_final)

    joblib.dump(final_clf, os.path.join(args.out_dir, "logreg.joblib"))
    np.save(os.path.join(args.out_dir, "node_ids.npy"), np.array(list(final_embeddings.keys())))
    np.save(os.path.join(args.out_dir, "embeddings.npy"), np.stack(list(final_embeddings.values())))

    metadata = {
        "model_version": "node2vec_logreg_v1",
        "holdout_auc": float(auc),
        "holdout_precision_at_k": float(precision_at_k),
        "holdout_k": k,
        "holdout_cutoff_date": str(cutoff),
        "n_new_edges_in_holdout": len(new_edges),
        "final_graph_nodes": final_G.number_of_nodes(),
        "final_graph_edges": final_G.number_of_edges(),
    }
    with open(os.path.join(args.out_dir, "lead_rec_metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\nArtifacts written to {os.path.abspath(args.out_dir)}")
    print(json.dumps(metadata, indent=2))

    conn.close()


if __name__ == "__main__":
    main()