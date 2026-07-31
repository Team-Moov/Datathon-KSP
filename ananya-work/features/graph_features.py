"""
graph_features.py
==================
Builds the co-offending network from case_person_role and computes:
  - Louvain community detection (surfaces cells/sub-groups)
  - PageRank centrality (surfaces the operational leader -- tightly
    connected to other important people)
  - Betweenness centrality (surfaces the broker -- bridges two otherwise
    disconnected cells; in practice tends to catch messengers/money-movers)

These are two DIFFERENT signals on purpose, per the design doc -- don't
collapse them into one "importance" number. A person can be a high-
betweenness broker with modest PageRank, or vice versa, and that
distinction matters to an investigator.

Weighting note (read before changing this):
  Co-occurrence weight means "how many times these two people were
  co-accused together" -- higher weight = STRONGER tie.
  - PageRank treats edge weight as flow/importance: higher weight ->
    more influence transferred. No transformation needed.
  - Betweenness treats edge weight as DISTANCE for shortest-path
    computation: higher weight would normally mean "farther apart",
    which is backwards for us. We invert (distance = 1 / weight) before
    computing betweenness so that a strong tie counts as "close", not
    "far". Skipping this inversion is a common, subtle correctness bug --
    don't remove it without re-deriving why.

Temporal snapshotting:
  build_coffending_graph(as_of_date=...) filters to incidents on or
  before that date. This is what makes the lead-recommendation holdout
  validation possible later: build the graph as of 6 months ago, see
  which edges the model would have predicted, compare against what
  actually appeared since.

Output:
  Writes one row per person per run to person_graph_metric (append-only,
  versioned by graph_version -- see migrations/001_person_graph_metric.sql).
  Does NOT overwrite prior runs.
"""

import argparse
from datetime import date

import networkx as nx
import psycopg2
import psycopg2.extras

from graph_utils import build_multiplex_graph


def build_coffending_graph(conn, as_of_date: date | None = None) -> nx.Graph:
    """Thin wrapper over the shared multiplex graph builder, restricted to
    co-offending edges only. Kept as its own function (rather than inlining
    the call everywhere) so this module's public API doesn't change even
    though the actual graph construction now lives in graph_utils.py --
    that's the single source of truth for how any edge type gets built,
    shared with the lead-recommendation model instead of duplicated.
    """
    return build_multiplex_graph(conn, as_of_date=as_of_date, include_mo_edges=False, include_financial_edges=False)


def compute_communities(G: nx.Graph) -> dict[str, str]:
    communities = nx.community.louvain_communities(G, weight="weight", seed=42)
    assignment = {}
    for i, community in enumerate(communities):
        cid = f"C{i:03d}"
        for person_id in community:
            assignment[person_id] = cid
    return assignment


def compute_centrality(G: nx.Graph) -> tuple[dict[str, float], dict[str, float]]:
    pagerank = nx.pagerank(G, weight="weight")

    # betweenness needs DISTANCE, so invert the strength weight (see module docstring)
    G_dist = G.copy()
    for u, v, data in G_dist.edges(data=True):
        data["distance"] = 1.0 / data["weight"]
    betweenness = nx.betweenness_centrality(G_dist, weight="distance", normalized=True)

    return pagerank, betweenness


def write_metrics(conn, pagerank, betweenness, communities, graph_version: str):
    cur = conn.cursor()
    all_person_ids = set(pagerank) | set(betweenness) | set(communities)
    rows = [
        (pid, pagerank.get(pid), betweenness.get(pid), communities.get(pid), graph_version)
        for pid in all_person_ids
    ]
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO person_graph_metric (person_id, pagerank, betweenness, community_id, graph_version)
           VALUES %s""",
        rows,
    )
    conn.commit()
    cur.close()
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--as-of-date", default=None, help="YYYY-MM-DD, optional temporal cutoff")
    ap.add_argument("--graph-version", default=None)
    args = ap.parse_args()

    as_of = date.fromisoformat(args.as_of_date) if args.as_of_date else None
    graph_version = args.graph_version or f"coffending_v1_asof_{as_of or 'latest'}"

    conn = psycopg2.connect(args.dsn)
    G = build_coffending_graph(conn, as_of_date=as_of)
    print(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges, "
          f"{nx.number_connected_components(G)} connected components")

    communities = compute_communities(G)
    pagerank, betweenness = compute_centrality(G)
    n_written = write_metrics(conn, pagerank, betweenness, communities, graph_version)
    print(f"Communities found: {len(set(communities.values()))}")
    print(f"Wrote {n_written} rows to person_graph_metric (graph_version={graph_version})")

    conn.close()


if __name__ == "__main__":
    main()
