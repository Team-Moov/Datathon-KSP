"""
graph_utils.py
==============
Builds the multiplex person-person graph: co-offending edges (from
case_person_role), MO-similarity edges (from mo_linkage_cluster -- persons
whose offenses were clustered together by the MO-linkage model), and
financial edges (from financial_transaction). Each edge type stays
distinguishable, not collapsed into one generic "associated with" weight --
per the design doc, a financial link and a co-arrest are different
strengths of evidence.

IMPORTANT -- temporal leakage note for MO-similarity edges:
  MO clustering (mo_linkage_cluster) was computed once over the WHOLE
  offense corpus, not re-run on a time-sliced basis. That means MO-
  similarity edges can't honestly be included in a "graph as of 6 months
  ago" snapshot without leaking future information into the past view.
  So: `include_mo_edges` should be False whenever you're building a
  historical/holdout graph for validation, and True only for the current,
  full-data graph used for actual inference. This is enforced by the
  caller (train_node2vec_logreg.py), not by this function, so read the
  call sites before assuming a graph is leakage-free.
"""

import re
from datetime import date

import networkx as nx


def _account_to_person_id(account: str) -> str:
    # accounts are minted as f"ACC{person_id[1:]}" in the generator, e.g.
    # person P00001 -> account ACC00001. Invert that pattern.
    m = re.match(r"^ACC(\d+)$", account)
    if not m:
        return None
    return f"P{m.group(1)}"


def _add_or_accumulate_edge(G, a, b, weight, edge_type):
    if a == b:
        return
    if G.has_edge(a, b):
        G[a][b]["weight"] += weight
        G[a][b].setdefault("edge_types", {}).setdefault(edge_type, 0)
        G[a][b]["edge_types"][edge_type] += weight
    else:
        G.add_edge(a, b, weight=weight, edge_types={edge_type: weight})


def build_multiplex_graph(
    conn,
    as_of_date: date | None = None,
    include_mo_edges: bool = False,
    include_financial_edges: bool = True,
) -> nx.Graph:
    G = nx.Graph()
    cur = conn.cursor()

    # --- co-offending edges ---
    query = """
        SELECT cpr.incident_id, cpr.person_id
        FROM case_person_role cpr
        JOIN incident i ON i.incident_id = cpr.incident_id
        WHERE cpr.role = 'accused'
    """
    params = []
    if as_of_date is not None:
        query += " AND i.date_occurred <= %s"
        params.append(as_of_date)
    cur.execute(query, params)
    by_incident = {}
    for incident_id, person_id in cur.fetchall():
        by_incident.setdefault(incident_id, []).append(person_id)
    for people in by_incident.values():
        uniq = sorted(set(people))
        for i in range(len(uniq)):
            for j in range(i + 1, len(uniq)):
                _add_or_accumulate_edge(G, uniq[i], uniq[j], 1.0, "co_offending")

    # --- financial edges ---
    if include_financial_edges:
        fquery = "SELECT from_account, to_account, tx_date FROM financial_transaction"
        fparams = []
        if as_of_date is not None:
            fquery += " WHERE tx_date <= %s"
            fparams.append(as_of_date)
        cur.execute(fquery, fparams)
        for from_acc, to_acc, _ in cur.fetchall():
            pa, pb = _account_to_person_id(from_acc), _account_to_person_id(to_acc)
            if pa and pb:
                _add_or_accumulate_edge(G, pa, pb, 1.0, "financial")

    # --- MO-similarity edges (see leakage note in module docstring) ---
    if include_mo_edges:
        cur.execute("""
            SELECT mlc.cluster_id, cpr.person_id, mlc.similarity_score
            FROM mo_linkage_cluster mlc
            JOIN offense o ON o.offense_id = mlc.offense_id
            JOIN case_person_role cpr ON cpr.incident_id = o.incident_id AND cpr.role = 'accused'
        """)
        by_cluster = {}
        for cluster_id, person_id, sim in cur.fetchall():
            by_cluster.setdefault(cluster_id, []).append((person_id, float(sim) if sim else 0.0))
        for members in by_cluster.values():
            uniq_people = sorted(set(p for p, _ in members))
            if len(uniq_people) < 2:
                continue
            avg_sim = sum(s for _, s in members) / len(members)
            for i in range(len(uniq_people)):
                for j in range(i + 1, len(uniq_people)):
                    _add_or_accumulate_edge(G, uniq_people[i], uniq_people[j], avg_sim, "mo_similarity")

    cur.close()
    return G