import argparse
import asyncio

import psycopg2

from app.core.graph_db import graph_db
from app.services.graph_sync_service import GraphSyncService
from scripts.ml_bridge.id_map import to_uuid


async def sync_person_graph_metrics(ml_conn, graph_version=None):
    cur = ml_conn.cursor()
    if graph_version:
        cur.execute(
            "SELECT person_id, pagerank, betweenness, community_id FROM person_graph_metric WHERE graph_version = %s",
            (graph_version,),
        )
    else:
        cur.execute("""
            SELECT DISTINCT ON (person_id) person_id, pagerank, betweenness, community_id
            FROM person_graph_metric
            ORDER BY person_id, computed_at DESC
        """)
    rows = cur.fetchall()
    for person_id, pagerank, betweenness, community_id in rows:
        target_id = str(to_uuid(person_id))
        await graph_db.execute_query(
            """
            MERGE (p:Person {id: $person_id})
            SET p.pagerank = $pagerank,
                p.betweenness = $betweenness,
                p.community_id = $community_id,
                p.centrality_updated_at = datetime()
            """,
            {
                "person_id": target_id,
                "pagerank": float(pagerank) if pagerank is not None else 0.0,
                "betweenness": float(betweenness) if betweenness is not None else 0.0,
                "community_id": community_id or "",
            },
        )
    cur.close()
    return len(rows)


async def sync_predicted_links(ml_conn):
    cur = ml_conn.cursor()
    cur.execute("""
        SELECT person_id_a, person_id_b, confidence, source_tool, evidence, model_version
        FROM predicted_link
    """)
    rows = cur.fetchall()
    sync_service = GraphSyncService()
    for person_id_a, person_id_b, confidence, source_tool, evidence, model_version in rows:
        await sync_service.upsert_predicted_link(
            person_a_id=str(to_uuid(person_id_a)),
            person_b_id=str(to_uuid(person_id_b)),
            confidence=float(confidence),
            model_version=model_version,
            source_tool=source_tool,
            evidence=evidence,
        )
    cur.close()
    return len(rows)


async def run(ml_dsn, graph_version=None):
    ml_conn = psycopg2.connect(ml_dsn)
    n_metrics = await sync_person_graph_metrics(ml_conn, graph_version)
    n_links = await sync_predicted_links(ml_conn)
    ml_conn.close()
    print(f"Synced {n_metrics} person_graph_metric rows and {n_links} predicted_link rows to Neo4j")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml-dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--graph-version", default=None)
    args = ap.parse_args()
    asyncio.run(run(args.ml_dsn, args.graph_version))