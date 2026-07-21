"""
infer.py
========
Applies the trained MO-linkage projection head to every offense (not just
the ones with known ground-truth series -- in production you never know
which incidents belong to a series in advance, that's the whole point).

Clustering is done WITHIN each crime_head group, not across the whole
corpus -- an MO cluster spanning "Theft" and "Cheating" isn't a
meaningful investigative signal, and keeping crime heads separate also
means the model doesn't need to have learned to distinguish crime types
from scratch (TF-IDF vocabulary already does most of that trivially).

Writes to mo_linkage_cluster: append-only, tagged with model_version, so
re-running this after a model update produces a new set of rows rather
than silently overwriting the last run's cluster assignments.
"""

import argparse
import json
import os

import joblib
import numpy as np
import psycopg2
import psycopg2.extras
import torch
import torch.nn as nn
from sklearn.cluster import AgglomerativeClustering


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
        return nn.functional.normalize(z, dim=1)


def load_artifacts(artifacts_dir):
    with open(os.path.join(artifacts_dir, "metadata.json")) as f:
        metadata = json.load(f)
    vectorizer = joblib.load(os.path.join(artifacts_dir, "tfidf_vectorizer.joblib"))
    model = ProjectionHead(metadata["in_dim"], metadata["hidden_dim"], metadata["out_dim"])
    model.load_state_dict(torch.load(os.path.join(artifacts_dir, "projection_head.pt")))
    model.eval()
    return vectorizer, model, metadata


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--artifacts-dir", default="./artifacts")
    args = ap.parse_args()

    vectorizer, model, metadata = load_artifacts(args.artifacts_dir)
    threshold = metadata["cluster_distance_threshold"]
    model_version = metadata["model_version"]

    conn = psycopg2.connect(args.dsn)
    cur = conn.cursor()
    cur.execute("SELECT offense_id, crime_head, mo_text FROM offense WHERE mo_text IS NOT NULL")
    rows = cur.fetchall()

    by_crime_head = {}
    for offense_id, crime_head, mo_text in rows:
        by_crime_head.setdefault(crime_head, []).append((offense_id, mo_text))

    all_cluster_rows = []
    for crime_head, items in by_crime_head.items():
        if len(items) < 2:
            continue
        offense_ids = [i[0] for i in items]
        texts = [i[1] for i in items]
        tfidf_vecs = vectorizer.transform(texts).toarray()
        with torch.no_grad():
            embeddings = model(torch.tensor(tfidf_vecs, dtype=torch.float32)).numpy()

        clustering = AgglomerativeClustering(
            n_clusters=None, distance_threshold=threshold, metric="cosine", linkage="average"
        )
        labels = clustering.fit_predict(embeddings)

        # similarity_score = each offense's average similarity to others in its cluster
        sims = embeddings @ embeddings.T
        for i, offense_id in enumerate(offense_ids):
            cluster_members = np.where(labels == labels[i])[0]
            others = [j for j in cluster_members if j != i]
            sim_score = float(np.mean([sims[i, j] for j in others])) if others else 1.0
            cluster_id = f"{crime_head.replace(' ', '_').replace('/', '_')}_CL{labels[i]:03d}"
            all_cluster_rows.append((offense_id, cluster_id, round(sim_score, 4), model_version))

    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO mo_linkage_cluster (offense_id, cluster_id, similarity_score, model_version)
           VALUES %s""",
        all_cluster_rows,
    )
    conn.commit()

    n_clusters = len(set(r[1] for r in all_cluster_rows))
    from collections import Counter
    cluster_sizes = Counter(r[1] for r in all_cluster_rows)
    n_multi_member_clusters = sum(1 for v in cluster_sizes.values() if v > 1)

    print(f"Wrote {len(all_cluster_rows)} rows to mo_linkage_cluster (model_version={model_version})")
    print(f"Total clusters: {n_clusters}, of which {n_multi_member_clusters} have 2+ members")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
