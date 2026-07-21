"""
link_pred_holdout.py
=====================
Temporal holdout construction and evaluation for the lead-recommendation
model, pulled out of train_node2vec_logreg.py for the same reason as
survival_eval.py -- one source of truth, reusable by anything that wants
to re-check link-prediction quality later without re-deriving the split
logic from scratch.

The core idea (repeated here because it's easy to get backwards): build
the graph as it looked at some past cutoff, train on it, then check
whether high-scoring predictions among people who existed then actually
became real edges by the end of the full data window. The graph's own
edge-formation history over time is the label -- no external ground
truth needed.
"""

from datetime import date, timedelta

import numpy as np
from sklearn.metrics import roc_auc_score


def get_date_range(conn):
    cur = conn.cursor()
    cur.execute("SELECT MIN(date_occurred), MAX(date_occurred) FROM incident")
    lo, hi = cur.fetchone()
    # some drivers don't reliably type-convert aggregate function results
    # (e.g. SQLite's MIN/MAX on a DATE column can come back as a plain
    # string even with converters registered) -- defensive, harmless under
    # Postgres where these are already date objects
    if isinstance(lo, str):
        lo = date.fromisoformat(lo)
    if isinstance(hi, str):
        hi = date.fromisoformat(hi)
    cur.close()
    return lo, hi


def compute_cutoff(conn, holdout_days: int = 180) -> date:
    _, hi = get_date_range(conn)
    return hi - timedelta(days=holdout_days)


def find_new_edges(past_G, full_G):
    """Edges present in the full graph, both endpoints existed in the past
    graph, but the edge itself didn't -- i.e. new ties formed after the
    holdout cutoff."""
    past_nodes = set(past_G.nodes())
    return [
        (u, v) for u, v in full_G.edges()
        if u in past_nodes and v in past_nodes and not past_G.has_edge(u, v)
    ]


def sample_non_edges(G, nodes, n, exclude_pairs=None, seed=42):
    import random
    rng = random.Random(seed)
    exclude_pairs = exclude_pairs or set()
    nodes = list(nodes)
    pairs = set()
    attempts = 0
    while len(pairs) < n and attempts < n * 50:
        attempts += 1
        a, b = rng.sample(nodes, 2)
        key = tuple(sorted((a, b)))
        if key in exclude_pairs or G.has_edge(a, b):
            continue
        pairs.add(key)
    return list(pairs)


def evaluate_holdout(clf, embeddings: dict, new_edges: list, non_edges: list, k: int = 20) -> dict:
    """AUC-ROC and precision@k on the true holdout set -- the model was
    never trained on anything past the cutoff, so this is a genuinely
    causal evaluation, not leakage dressed up as one."""
    test_pairs = new_edges + non_edges
    y_test = np.array([1] * len(new_edges) + [0] * len(non_edges))
    X_test = np.stack([embeddings[u] * embeddings[v] for u, v in test_pairs])
    y_scores = clf.predict_proba(X_test)[:, 1]

    auc = roc_auc_score(y_test, y_scores)
    order = np.argsort(-y_scores)
    k = min(k, len(order))
    precision_at_k = float(y_test[order[:k]].mean())
    chance_level = len(new_edges) / len(test_pairs) if test_pairs else 0.0

    return {
        "auc_roc": float(auc),
        "precision_at_k": precision_at_k,
        "k": k,
        "chance_level": chance_level,
        "n_new_edges": len(new_edges),
        "n_non_edges_sampled": len(non_edges),
    }
