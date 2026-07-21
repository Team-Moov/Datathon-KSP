import argparse
import asyncio

from scripts.ml_bridge import sync_entities, sync_risk_and_mo, sync_graph_and_links


async def run(ml_dsn, graph_version):
    await sync_entities.run(ml_dsn)
    await sync_risk_and_mo.run(ml_dsn)
    await sync_graph_and_links.run(ml_dsn, graph_version)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml-dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    ap.add_argument("--graph-version", default=None)
    args = ap.parse_args()
    asyncio.run(run(args.ml_dsn, args.graph_version))