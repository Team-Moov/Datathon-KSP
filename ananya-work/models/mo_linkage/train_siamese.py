"""
train_siamese.py
=================
Trains a contrastive projection head that maps MO narrative text into an
embedding space where same-offender incidents (per mo_linkage_series ground
truth) sit close together and different-offender incidents sit apart.

HONEST LIMITATION, READ THIS FIRST:
  A proper version of this starts from a pretrained sentence-transformer
  (e.g. a multilingual/Indic model, given the real system needs Kannada
  coverage) and fine-tunes on top of it. This sandbox cannot reach
  huggingface.co to download one -- network is restricted to a fixed
  allowlist that doesn't include it. So the base representation here is
  TF-IDF (fully offline, no download needed), with a real trained MLP
  projection head on top using a margin-based contrastive loss. This is
  genuine trained ML, not a shortcut -- but TF-IDF has a real ceiling:
  it only recognizes vocabulary it's seen, so it won't generalize to
  paraphrases using entirely different words the way a pretrained sentence
  encoder would. UPGRADE PATH: once there's real network access, swap
  `TfidfVectorizer` + the projection head for
  `sentence-transformers` fine-tuning (e.g. paraphrase-multilingual-
  MiniLM-L12-v2, which has Indic-language coverage) -- the contrastive
  training loop and evaluation below don't need to change, only the base
  embedding step.

WHAT THE MODEL NEVER SEES:
  `mo_signature` (the ground-truth "entry:rear window" style tag) and
  `series_id` are used ONLY to decide which pairs are positive/negative
  during training and for evaluation. They are never fed into the model as
  input features -- the model only ever sees `mo_text`, the free narrative.
  That's what makes the recall@k evaluation below a fair test rather than
  leakage: the model has to recover the signature from text alone.

Usage:
    python train_siamese.py --dsn postgresql://crimeportal:crimeportal@localhost/crimeportal \
        --out-dir ./artifacts
"""

import argparse
import itertools
import json
import os
import random

import joblib
import numpy as np
import psycopg2
import torch
import torch.nn as nn
from sklearn.feature_extraction.text import TfidfVectorizer

SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_series_offenses(conn):
    """Every offense that belongs to a known MO-linkage series, with its text."""
    cur = conn.cursor()
    cur.execute("""
        SELECT mls.series_id, o.offense_id, o.crime_head, o.mo_text
        FROM mo_linkage_series mls
        JOIN offense o ON o.offense_id = mls.offense_id
    """)
    rows = cur.fetchall()
    cur.close()
    return [{"series_id": r[0], "offense_id": r[1], "crime_head": r[2], "mo_text": r[3]} for r in rows]


def load_all_offense_text(conn):
    """All offense narrative text, used only to fit the TF-IDF vocabulary
    on a realistic corpus (not just the labeled series)."""
    cur = conn.cursor()
    cur.execute("SELECT offense_id, mo_text FROM offense WHERE mo_text IS NOT NULL")
    rows = cur.fetchall()
    cur.close()
    return rows


# ---------------------------------------------------------------------------
# Pair construction
# ---------------------------------------------------------------------------

def series_train_val_split(records, val_frac=0.2):
    series_ids = sorted(set(r["series_id"] for r in records))
    rng = random.Random(SEED)
    rng.shuffle(series_ids)
    n_val = max(1, int(len(series_ids) * val_frac))
    val_series = set(series_ids[:n_val])
    train_series = set(series_ids[n_val:])
    train = [r for r in records if r["series_id"] in train_series]
    val = [r for r in records if r["series_id"] in val_series]
    return train, val


def build_pairs(records, neg_per_pos=1.0, hard_neg_frac=0.7):
    """Positive pairs = same series_id. Negatives are mostly HARD (same
    crime_head, different series -- these are the pairs that actually
    teach the model something) with a smaller share of easy negatives
    (different crime_head) for regularization."""
    by_series = {}
    for r in records:
        by_series.setdefault(r["series_id"], []).append(r)

    pos_pairs = []
    for series_id, items in by_series.items():
        for a, b in itertools.combinations(items, 2):
            pos_pairs.append((a["offense_id"], b["offense_id"], 1))

    rng = random.Random(SEED)
    n_neg = int(len(pos_pairs) * neg_per_pos)
    n_hard = int(n_neg * hard_neg_frac)
    n_easy = n_neg - n_hard

    by_crime_head = {}
    for r in records:
        by_crime_head.setdefault(r["crime_head"], []).append(r)

    neg_pairs = []
    attempts = 0
    while len(neg_pairs) < n_hard and attempts < n_hard * 20:
        attempts += 1
        ch = rng.choice(list(by_crime_head.keys()))
        pool = by_crime_head[ch]
        if len(pool) < 2:
            continue
        a, b = rng.sample(pool, 2)
        if a["series_id"] != b["series_id"]:
            neg_pairs.append((a["offense_id"], b["offense_id"], 0))

    attempts = 0
    while len(neg_pairs) < n_hard + n_easy and attempts < n_easy * 20:
        attempts += 1
        a, b = rng.sample(records, 2)
        if a["crime_head"] != b["crime_head"]:
            neg_pairs.append((a["offense_id"], b["offense_id"], 0))

    all_pairs = pos_pairs + neg_pairs
    rng.shuffle(all_pairs)
    return all_pairs


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class ProjectionHead(nn.Module):
    def __init__(self, in_dim, hidden_dim=256, out_dim=64):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, out_dim),
        )

    def forward(self, x):
        z = self.net(x)
        return nn.functional.normalize(z, dim=1)  # L2-normalize -> cosine sim = dot product


def contrastive_loss(emb_a, emb_b, labels, margin=0.5):
    cos_sim = (emb_a * emb_b).sum(dim=1)
    dist = 1 - cos_sim
    pos_loss = labels * dist.pow(2)
    neg_loss = (1 - labels) * torch.clamp(margin - dist, min=0).pow(2)
    return (pos_loss + neg_loss).mean()


# ---------------------------------------------------------------------------
# Evaluation: same-series retrieval, recall@k
# ---------------------------------------------------------------------------

def evaluate_recall_at_k(embeddings, offense_ids, id_to_series, ks=(1, 3)):
    emb = np.stack([embeddings[oid] for oid in offense_ids])
    sims = emb @ emb.T
    np.fill_diagonal(sims, -np.inf)

    results = {k: 0 for k in ks}
    n = len(offense_ids)
    for i, oid in enumerate(offense_ids):
        true_series = id_to_series[oid]
        order = np.argsort(-sims[i])
        for k in ks:
            top_k_ids = [offense_ids[j] for j in order[:k]]
            if any(id_to_series[tid] == true_series for tid in top_k_ids):
                results[k] += 1
    return {k: results[k] / n for k in ks}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--out-dir", default="./artifacts")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)

    conn = psycopg2.connect(args.dsn)
    series_records = load_series_offenses(conn)
    all_text_rows = load_all_offense_text(conn)
    conn.close()

    print(f"Loaded {len(series_records)} offenses across "
          f"{len(set(r['series_id'] for r in series_records))} MO-linkage series")

    # fit TF-IDF on the full offense corpus, not just labeled series -- more realistic vocabulary
    vectorizer = TfidfVectorizer(max_features=2000, ngram_range=(1, 2), stop_words="english")
    all_texts = [r[1] for r in all_text_rows]
    vectorizer.fit(all_texts)

    id_to_text = {oid: text for oid, text in all_text_rows}
    id_to_vec = {oid: vectorizer.transform([id_to_text[oid]]).toarray()[0] for oid in
                 [r["offense_id"] for r in series_records]}

    train_records, val_records = series_train_val_split(series_records, val_frac=0.2)
    print(f"Train series offenses: {len(train_records)}, Val series offenses: {len(val_records)}")

    train_pairs = build_pairs(train_records)
    print(f"Train pairs: {len(train_pairs)} "
          f"({sum(1 for p in train_pairs if p[2] == 1)} positive, "
          f"{sum(1 for p in train_pairs if p[2] == 0)} negative)")

    in_dim = len(vectorizer.vocabulary_)
    model = ProjectionHead(in_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)

    def pairs_to_tensors(pairs):
        a = torch.tensor(np.stack([id_to_vec[p[0]] for p in pairs]), dtype=torch.float32)
        b = torch.tensor(np.stack([id_to_vec[p[1]] for p in pairs]), dtype=torch.float32)
        y = torch.tensor([p[2] for p in pairs], dtype=torch.float32)
        return a, b, y

    a_t, b_t, y_t = pairs_to_tensors(train_pairs)

    # baseline: raw TF-IDF cosine similarity, no learned projection -- this is
    # what we're trying to beat, so we know the projection head is earning its keep
    val_ids = [r["offense_id"] for r in val_records]
    id_to_series = {r["offense_id"]: r["series_id"] for r in val_records}
    raw_embeddings = {oid: id_to_vec[oid] / (np.linalg.norm(id_to_vec[oid]) + 1e-9) for oid in val_ids}
    baseline_recall = evaluate_recall_at_k(raw_embeddings, val_ids, id_to_series)
    print(f"Baseline (raw TF-IDF cosine) val recall@k: {baseline_recall}")

    model.train()
    for epoch in range(args.epochs):
        optimizer.zero_grad()
        emb_a = model(a_t)
        emb_b = model(b_t)
        loss = contrastive_loss(emb_a, emb_b, y_t)
        loss.backward()
        optimizer.step()
        if (epoch + 1) % 10 == 0:
            print(f"  epoch {epoch+1}/{args.epochs}  loss={loss.item():.4f}")

    model.eval()
    with torch.no_grad():
        val_embeddings = {}
        for oid in val_ids:
            vec = torch.tensor(id_to_vec[oid], dtype=torch.float32).unsqueeze(0)
            val_embeddings[oid] = model(vec).squeeze(0).numpy()

    trained_recall = evaluate_recall_at_k(val_embeddings, val_ids, id_to_series)
    print(f"Trained projection val recall@k:      {trained_recall}")

    # tune the clustering distance threshold on validation data (known series
    # labels) so infer.py doesn't have to guess a cut point later
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import adjusted_rand_score

    val_matrix = np.stack([val_embeddings[oid] for oid in val_ids])
    true_labels = [id_to_series[oid] for oid in val_ids]
    best_threshold, best_ari = None, -1
    for threshold in np.arange(0.02, 1.0, 0.02):
        clustering = AgglomerativeClustering(
            n_clusters=None, distance_threshold=threshold, metric="cosine", linkage="average"
        )
        pred_labels = clustering.fit_predict(val_matrix)
        ari = adjusted_rand_score(true_labels, pred_labels)
        if ari > best_ari:
            best_ari, best_threshold = ari, threshold
    print(f"Best clustering distance_threshold={best_threshold:.2f}  (adjusted_rand_score={best_ari:.3f} on val series)")

    # save artifacts
    joblib.dump(vectorizer, os.path.join(args.out_dir, "tfidf_vectorizer.joblib"))
    torch.save(model.state_dict(), os.path.join(args.out_dir, "projection_head.pt"))
    metadata = {
        "model_version": "mo_linkage_tfidf_contrastive_v1",
        "in_dim": in_dim,
        "hidden_dim": 256,
        "out_dim": 64,
        "baseline_recall_at_k": baseline_recall,
        "trained_recall_at_k": trained_recall,
        "cluster_distance_threshold": float(best_threshold),
        "cluster_threshold_ari": float(best_ari),
        "n_train_pairs": len(train_pairs),
        "n_series_total": len(set(r["series_id"] for r in series_records)),
    }
    with open(os.path.join(args.out_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"\nArtifacts written to {os.path.abspath(args.out_dir)}")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
