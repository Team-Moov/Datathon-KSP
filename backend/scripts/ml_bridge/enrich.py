"""
Data-gap enrichment pass over bridge-loaded ML data. Idempotent.

Closes four gaps so downstream analytics show real data instead of empty/sparse:
  1. Districts   — create backend District rows for Ananya's 31 districts
  2. Case geo    — backfill district_id + synthesized lat/long on cases (Hawkes needs geo)
  3. Graph edges — push ACCUSED_IN co-offending edges + Person names into Neo4j
                   (community detection & the predicted-link name both need these)
  4. Aggregates  — sync district_socioeconomic + crime_stat_aggregate (sociological/trends)

Coordinates are synthesized deterministically within Karnataka's bounding box,
clustered per district — enough spatial signal for the point-process forecast,
clearly synthetic (never real crime-scene coordinates).

Run: docker compose exec api python -m scripts.ml_bridge.enrich --ml-dsn /tmp/ml_source.db
"""

import argparse
import asyncio
import hashlib

from sqlalchemy import select, text

from app.core.database import AdminSessionFactory
from app.core.graph_db import graph_db
from app.models.case import CaseMaster, CrimeHead
from app.models.socio import CrimeStatAggregate, SocioEconomicIndicator
from app.models.unit import District, State
from scripts.ml_bridge.id_map import to_uuid
from scripts.ml_bridge.ml_conn import open_ml_conn

_KA_LAT = (11.6, 18.4)
_KA_LON = (74.1, 78.5)


def _coord(seed: str) -> tuple:
    h = int(hashlib.sha1(seed.encode()).hexdigest(), 16)
    lat = _KA_LAT[0] + ((h % 100000) / 100000) * (_KA_LAT[1] - _KA_LAT[0])
    lon = _KA_LON[0] + (((h // 100000) % 100000) / 100000) * (_KA_LON[1] - _KA_LON[0])
    return round(lat, 5), round(lon, 5)


async def sync_districts(session, ml) -> dict:
    cur = ml.cursor()
    cur.execute("SELECT district_id, district_name FROM district")
    rows = cur.fetchall()
    cur.close()
    state = (await session.execute(select(State).limit(1))).scalar_one_or_none()
    if state is None:
        state = State(name="Karnataka", code="KA")
        session.add(state)
        await session.flush()
    lookup = {}
    for slug, name in rows:
        d = (await session.execute(select(District).where(District.code == str(slug)[:20]))).scalar_one_or_none()
        if d is None:
            d = (await session.execute(select(District).where(District.name.ilike(name)))).scalar_one_or_none()
        if d is None:
            d = District(name=name, code=str(slug)[:20], state_id=state.id)
            session.add(d)
            await session.flush()
        lookup[slug] = d.id
    return lookup


async def backfill_case_geo(session, ml, dlookup) -> int:
    cur = ml.cursor()
    cur.execute("SELECT incident_id, district_id FROM incident")
    rows = cur.fetchall()
    cur.close()
    n = 0
    for incident_id, slug in rows:
        did = dlookup.get(slug)
        if did is None:
            continue
        blat, blon = _coord("dist:" + str(slug))
        jlat, jlon = _coord(str(incident_id))
        lat = round(blat * 0.75 + jlat * 0.25, 5)
        lon = round(blon * 0.75 + jlon * 0.25, 5)
        await session.execute(
            text("UPDATE case_master SET district_id=:d, latitude=:la, longitude=:lo WHERE id=:id"),
            {"d": did, "la": lat, "lo": lon, "id": str(to_uuid(incident_id))},
        )
        n += 1
    return n


async def sync_socio(session, ml, dlookup) -> int:
    cur = ml.cursor()
    cur.execute(
        "SELECT district_id, year, literacy_pct, unemployment_pct, urbanization_pct, "
        "sex_ratio, composite_stress_index FROM district_socioeconomic"
    )
    rows = cur.fetchall()
    cur.close()
    n = 0
    for slug, year, lit, unemp, urb, sr, csi in rows:
        did = dlookup.get(slug)
        if did is None:
            continue
        exists = (
            await session.execute(
                select(SocioEconomicIndicator).where(
                    SocioEconomicIndicator.district_id == did, SocioEconomicIndicator.year == year
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        session.add(
            SocioEconomicIndicator(
                district_id=did, year=year, literacy_rate=lit, unemployment_rate=unemp,
                urbanization_pct=urb, sex_ratio=sr, composite_stress_index=csi,
            )
        )
        n += 1
    return n


async def sync_crime_stat(session, ml, dlookup) -> int:
    cur = ml.cursor()
    cur.execute("SELECT district_id, year, crime_head, count FROM crime_stat_aggregate")
    rows = cur.fetchall()
    cur.close()
    ch_cache = {}
    n = 0
    for slug, year, chname, count in rows:
        did = dlookup.get(slug)
        if did is None:
            continue
        chid = ch_cache.get(chname)
        if chid is None:
            ch = (await session.execute(select(CrimeHead).where(CrimeHead.name == chname))).scalar_one_or_none()
            if ch is None:
                ch = CrimeHead(name=chname)
                session.add(ch)
                await session.flush()
            chid = ch.id
            ch_cache[chname] = chid
        exists = (
            await session.execute(
                select(CrimeStatAggregate).where(
                    CrimeStatAggregate.district_id == did,
                    CrimeStatAggregate.year == year,
                    CrimeStatAggregate.crime_head_id == chid,
                )
            )
        ).scalar_one_or_none()
        if exists:
            continue
        session.add(CrimeStatAggregate(district_id=did, year=year, crime_head_id=chid, count=count))
        n += 1
    return n


async def sync_graph_edges(ml) -> int:
    await graph_db.connect()
    try:
        cur = ml.cursor()
        cur.execute("SELECT person_id, name FROM person")
        persons = [{"id": str(to_uuid(pid)), "name": nm} for pid, nm in cur.fetchall()]
        for i in range(0, len(persons), 500):
            await graph_db.execute_query(
                "UNWIND $rows AS r MERGE (p:Person {id: r.id}) SET p.name = r.name",
                {"rows": persons[i:i + 500]},
            )
        cur.execute("SELECT incident_id, person_id, role FROM case_person_role")
        edges = [
            {"p": str(to_uuid(pid)), "i": str(to_uuid(iid))}
            for iid, pid, role in cur.fetchall()
            if str(role).lower() == "accused"
        ]
        cur.close()
        for i in range(0, len(edges), 500):
            await graph_db.execute_query(
                "UNWIND $rows AS r MERGE (p:Person {id: r.p}) MERGE (i:Incident {id: r.i}) "
                "MERGE (p)-[:ACCUSED_IN]->(i)",
                {"rows": edges[i:i + 500]},
            )
        return len(edges)
    finally:
        await graph_db.close()


async def run(ml_dsn):
    ml = open_ml_conn(ml_dsn)
    async with AdminSessionFactory() as session:
        dlookup = await sync_districts(session, ml)
        n_geo = await backfill_case_geo(session, ml, dlookup)
        n_socio = await sync_socio(session, ml, dlookup)
        n_stat = await sync_crime_stat(session, ml, dlookup)
        await session.commit()
    n_edges = await sync_graph_edges(ml)
    ml.close()
    print(
        f"districts={len(dlookup)} case_geo={n_geo} socio={n_socio} "
        f"crime_stat={n_stat} accused_edges={n_edges}"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml-dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    args = ap.parse_args()
    asyncio.run(run(args.ml_dsn))
