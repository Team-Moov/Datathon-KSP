import argparse
import asyncio

from scripts.ml_bridge.ml_conn import open_ml_conn
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AdminSessionFactory
from app.models.offender import CriminalHistory, RiskScore, MOLinkageCluster
from scripts.ml_bridge.id_map import to_uuid
from scripts.ml_bridge.ml_conn import as_dt
from scripts.ml_bridge.watermark import ensure_watermark_table, get_watermark, set_watermark


async def get_or_create_history_id(session: AsyncSession, person_id):
    result = await session.execute(
        select(CriminalHistory).where(CriminalHistory.person_id == person_id)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id
    history = CriminalHistory(person_id=person_id, human_verified=False)
    session.add(history)
    await session.flush()
    return history.id


async def sync_risk_scores(session: AsyncSession, ml_conn):
    since = await get_watermark(session, "risk_score")
    cur = ml_conn.cursor()
    query = """
        SELECT person_id, model_version, score, severity_history_component,
               centrality_component, mo_consistency_component, associate_risk_component, computed_at
        FROM risk_score
    """
    params = []
    if since is not None:
        query += " WHERE computed_at > %s"
        params.append(since)
    cur.execute(query, params)
    rows = cur.fetchall()

    latest = since
    for (person_id, model_version, score, sev, cen, mo, assoc, computed_at) in rows:
        computed_at = as_dt(computed_at)
        target_person_id = to_uuid(person_id)
        history_id = await get_or_create_history_id(session, target_person_id)
        session.add(RiskScore(
            criminal_history_id=history_id,
            model_version=model_version,
            score=float(score),
            chi_weighted_harm=float(sev or 0),
            network_centrality=float(cen or 0),
            mo_escalation_score=float(mo or 0),
            associate_risk_avg=float(assoc or 0),
            shap_decomposition={
                "severity_history": float(sev or 0),
                "centrality": float(cen or 0),
                "mo_consistency": float(mo or 0),
                "associate_risk": float(assoc or 0),
            },
            computed_at=computed_at,
        ))
        if latest is None or computed_at > latest:
            latest = computed_at

    await session.flush()
    if latest is not None:
        await set_watermark(session, "risk_score", latest)
    cur.close()
    return len(rows)


async def sync_mo_clusters(session: AsyncSession, ml_conn):
    since = await get_watermark(session, "mo_linkage_cluster")
    cur = ml_conn.cursor()
    query = """
        SELECT o.incident_id, mlc.cluster_id, mlc.similarity_score, mlc.model_version, mlc.computed_at
        FROM mo_linkage_cluster mlc
        JOIN offense o ON o.offense_id = mlc.offense_id
    """
    params = []
    if since is not None:
        query += " WHERE mlc.computed_at > %s"
        params.append(since)
    cur.execute(query, params)
    rows = cur.fetchall()

    latest = since
    for incident_id, cluster_id, similarity_score, model_version, computed_at in rows:
        computed_at = as_dt(computed_at)
        case_id = to_uuid(incident_id)
        session.add(MOLinkageCluster(
            case_id=case_id,
            cluster_id=cluster_id,
            similarity_score=float(similarity_score),
            model_version=model_version,
            computed_at=computed_at,
        ))
        if latest is None or computed_at > latest:
            latest = computed_at

    await session.flush()
    if latest is not None:
        await set_watermark(session, "mo_linkage_cluster", latest)
    cur.close()
    return len(rows)


async def run(ml_dsn):
    ml_conn = open_ml_conn(ml_dsn)
    async with AdminSessionFactory() as session:
        await ensure_watermark_table(session)
        n_risk = await sync_risk_scores(session, ml_conn)
        n_mo = await sync_mo_clusters(session, ml_conn)
        await session.commit()
    ml_conn.close()
    print(f"Synced {n_risk} new risk_score rows and {n_mo} new mo_linkage_cluster rows")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml-dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    args = ap.parse_args()
    asyncio.run(run(args.ml_dsn))