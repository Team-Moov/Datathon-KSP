import argparse
import asyncio

from scripts.ml_bridge.ml_conn import open_ml_conn
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AdminSessionFactory
from app.models.case import CaseMaster, CrimeHead, CrimeSubHead, GravityOffence
from app.models.person import Person, PersonCaseRole
from app.models.financial import FinancialTransaction
from app.models.unit import District
from app.models.enums import SourceType, PersonRole
from scripts.ml_bridge.id_map import to_uuid
from scripts.ml_bridge.ml_conn import as_date

HEINOUS_THRESHOLD = 50


async def build_district_lookup(session: AsyncSession, ml_conn) -> dict:
    cur = ml_conn.cursor()
    cur.execute("SELECT district_id, district_name FROM district")
    slug_to_name = {slug: name for slug, name in cur.fetchall()}
    cur.close()

    lookup = {}
    for slug, name in slug_to_name.items():
        result = await session.execute(select(District).where(District.code == slug))
        district = result.scalar_one_or_none()
        if district is None:
            result = await session.execute(select(District).where(District.name.ilike(name)))
            district = result.scalar_one_or_none()
        if district is not None:
            lookup[slug] = district.id
    return lookup


async def get_or_create_gravity_offence(session: AsyncSession, is_heinous: bool, avg_weight: float) -> int:
    label = "Heinous" if is_heinous else "Non-Heinous"
    result = await session.execute(select(GravityOffence).where(GravityOffence.label == label))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id
    row = GravityOffence(label=label, chi_weight=avg_weight)
    session.add(row)
    await session.flush()
    return row.id


async def get_or_create_crime_head(session: AsyncSession, name: str) -> int:
    result = await session.execute(select(CrimeHead).where(CrimeHead.name == name))
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id
    row = CrimeHead(name=name)
    session.add(row)
    await session.flush()
    return row.id


async def get_or_create_crime_sub_head(
    session: AsyncSession, crime_head_id: int, name: str, gravity_offence_id: int
) -> int:
    result = await session.execute(
        select(CrimeSubHead).where(CrimeSubHead.crime_head_id == crime_head_id, CrimeSubHead.name == name)
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        return existing.id
    row = CrimeSubHead(crime_head_id=crime_head_id, name=name, gravity_offence_id=gravity_offence_id)
    session.add(row)
    await session.flush()
    return row.id


async def build_crime_head_lookup(session: AsyncSession, ml_conn) -> dict:
    cur = ml_conn.cursor()
    cur.execute("SELECT crime_head, AVG(severity_weight) FROM offense GROUP BY crime_head")
    rows = cur.fetchall()
    cur.close()

    lookup = {}
    for crime_head, avg_weight in rows:
        avg_weight = float(avg_weight) if avg_weight is not None else 0.0
        is_heinous = avg_weight >= HEINOUS_THRESHOLD
        gravity_id = await get_or_create_gravity_offence(session, is_heinous, avg_weight)
        head_id = await get_or_create_crime_head(session, crime_head)
        sub_head_id = await get_or_create_crime_sub_head(session, head_id, crime_head, gravity_id)
        lookup[crime_head] = (head_id, sub_head_id)
    return lookup


async def sync_persons(session: AsyncSession, ml_conn):
    cur = ml_conn.cursor()
    cur.execute("SELECT person_id, name, age, sex, district_id, address_text FROM person")
    for person_id, name, age, sex, district_id, address_text in cur.fetchall():
        target_id = to_uuid(person_id)
        existing = await session.get(Person, target_id)
        if existing is not None:
            continue
        session.add(Person(
            id=target_id,
            full_name=name,
            age_at_registration=age,
            sex=sex,
            source_person_id=person_id,
            present_address=address_text,
        ))
    await session.flush()
    cur.close()


async def sync_cases_and_offenses(session: AsyncSession, ml_conn, district_lookup, crime_head_lookup):
    cur = ml_conn.cursor()
    cur.execute("SELECT incident_id, fir_number, district_id, date_occurred, date_reported, status FROM incident")
    for incident_id, fir_number, district_id, date_occurred, date_reported, status in cur.fetchall():
        target_id = to_uuid(incident_id)
        existing = await session.get(CaseMaster, target_id)
        if existing is None:
            session.add(CaseMaster(
                id=target_id,
                crime_no=fir_number,
                district_id=district_lookup.get(district_id),
                incident_from_date=as_date(date_occurred),
                date_reported=as_date(date_reported),
                source_type=SourceType.FIR,
            ))
    await session.flush()

    cur.execute("SELECT offense_id, incident_id, crime_head, mo_text, mo_signature, severity_weight FROM offense")
    for offense_id, incident_id, crime_head, mo_text, mo_signature, severity_weight in cur.fetchall():
        case_id = to_uuid(incident_id)
        case = await session.get(CaseMaster, case_id)
        if case is None:
            continue
        if case.brief_facts is None:
            case.brief_facts = mo_text
        head_id, sub_head_id = crime_head_lookup.get(crime_head, (None, None))
        if case.crime_head_id is None:
            case.crime_head_id = head_id
        if case.crime_sub_head_id is None:
            case.crime_sub_head_id = sub_head_id
    await session.flush()
    cur.close()


async def sync_case_person_roles(session: AsyncSession, ml_conn):
    cur = ml_conn.cursor()
    cur.execute("SELECT incident_id, person_id, role FROM case_person_role")
    for incident_id, person_id, role in cur.fetchall():
        case_id = to_uuid(incident_id)
        target_person_id = to_uuid(person_id)
        existing = await session.execute(
            select(PersonCaseRole).where(
                PersonCaseRole.case_id == case_id,
                PersonCaseRole.person_id == target_person_id,
                PersonCaseRole.role == PersonRole(role),
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue
        session.add(PersonCaseRole(
            case_id=case_id,
            person_id=target_person_id,
            role=PersonRole(role),
        ))
    await session.flush()
    cur.close()


async def sync_financial_transactions(session: AsyncSession, ml_conn):
    cur = ml_conn.cursor()
    cur.execute(
        "SELECT transaction_id, from_account, to_account, amount, tx_date, linked_person_id FROM financial_transaction"
    )
    for transaction_id, from_account, to_account, amount, tx_date, linked_person_id in cur.fetchall():
        target_id = to_uuid(transaction_id)
        existing = await session.get(FinancialTransaction, target_id)
        if existing is not None:
            continue
        session.add(FinancialTransaction(
            id=target_id,
            from_account=from_account,
            to_account=to_account,
            amount=amount,
            transaction_date=as_date(tx_date),
            linked_person_id=to_uuid(linked_person_id) if linked_person_id else None,
        ))
    await session.flush()
    cur.close()


async def run(ml_dsn):
    ml_conn = open_ml_conn(ml_dsn)
    async with AdminSessionFactory() as session:
        district_lookup = await build_district_lookup(session, ml_conn)
        crime_head_lookup = await build_crime_head_lookup(session, ml_conn)
        await sync_persons(session, ml_conn)
        await sync_cases_and_offenses(session, ml_conn, district_lookup, crime_head_lookup)
        await sync_case_person_roles(session, ml_conn)
        await sync_financial_transactions(session, ml_conn)
        await session.commit()
    ml_conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml-dsn", default="postgresql://crimeportal:crimeportal@localhost/crimeportal")
    args = ap.parse_args()
    asyncio.run(run(args.ml_dsn))