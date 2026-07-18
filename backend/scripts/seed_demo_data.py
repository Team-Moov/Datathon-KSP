"""
Demo seed data — reference lookups, one demo user per rank, and a handful of
linked sample cases so the Investigator Workspace / network explorer / financial
crime pages aren't empty on a fresh install.

Run from the backend/ directory:
    python -m scripts.seed_demo_data

Every relationship below traces back to a real column in the design doc's
schema (karnataka_crime_platform_design.md §3/§4/§9) — a PersonCaseRole
co-offending edge between two accused on the same case, and a shared
FinancialTransaction between them — nothing invented. Both are also pushed
into Neo4j through the same GraphSyncService the ingestion pipeline uses, so
the network explorer shows a real multi-node graph rather than isolated dots.
"""

import asyncio
import uuid
from datetime import date

import structlog
from sqlalchemy import select

from app.core.database import AsyncSessionFactory, init_db
from app.core.security import hash_password
from app.models.case import (
    Act,
    ActSectionAssociation,
    CaseMaster,
    CaseStageEvent,
    CaseStatusMaster,
    CrimeHead,
    CrimeSubHead,
    GravityOffence,
    Section,
)
from app.models.document import Document
from app.models.enums import (
    CaseStage,
    DocumentFormat,
    ExtractionMethod,
    FinancialAlertType,
    PersonRole,
    Role,
    Sex,
    SourceType,
)
from app.models.financial import FinancialTransaction
from app.models.offender import CriminalHistory, RiskScore
from app.models.person import Person, PersonCaseRole
from app.models.unit import District, State, Unit, UnitType
from app.models.user import User
from app.services.graph_sync_service import GraphSyncService

log = structlog.get_logger(__name__)

DEMO_PASSWORD = "Demo@12345"

_DEMO_USERS = [
    ("dgp@ksp.demo", "Rajendra Holla", Role.DGP, "DGP-0001"),
    ("sp@ksp.demo", "Meera Nayak", Role.SP, "SP-0007"),
    ("dsp@ksp.demo", "Arvind Kulkarni", Role.DSP, "DSP-0021"),
    ("inspector@ksp.demo", "Suresh Patil", Role.INSPECTOR, "INS-0134"),
    ("constable@ksp.demo", "Ravi Kumar", Role.CONSTABLE, "PC-4471"),
    ("analyst@ksp.demo", "Divya Shenoy", Role.CRIME_ANALYST, "CA-0009"),
    ("policymaker@ksp.demo", "Anil Deshpande", Role.POLICY_MAKER, "PM-0002"),
]

# Ranks tied to a posting — mirrors CaseRepository._DISTRICT_UNRESTRICTED_ROLES.
_DISTRICT_SCOPED_ROLES = {Role.CONSTABLE, Role.INSPECTOR}


async def _get_or_create(session, model, defaults=None, **lookup):
    result = await session.execute(select(model).filter_by(**lookup))
    obj = result.scalar_one_or_none()
    if obj is not None:
        return obj
    obj = model(**lookup, **(defaults or {}))
    session.add(obj)
    await session.flush()
    return obj


async def seed() -> None:
    await init_db()

    async with AsyncSessionFactory() as session:
        state = await _get_or_create(session, State, name="Karnataka", defaults={"code": "KA"})
        bengaluru = await _get_or_create(
            session, District, name="Bengaluru Urban", state_id=state.id, defaults={"code": "BLR"}
        )
        mysuru = await _get_or_create(
            session, District, name="Mysuru", state_id=state.id, defaults={"code": "MYS"}
        )

        station_type = await _get_or_create(session, UnitType, name="Police Station", defaults={"hierarchy_level": 3})
        circle_type = await _get_or_create(session, UnitType, name="Circle", defaults={"hierarchy_level": 2})

        blr_circle = await _get_or_create(
            session, Unit, name="Bengaluru East Circle", unit_type_id=circle_type.id, district_id=bengaluru.id
        )
        blr_station = await _get_or_create(
            session, Unit, name="Indiranagar PS", unit_type_id=station_type.id, district_id=bengaluru.id,
            defaults={"parent_unit_id": blr_circle.id},
        )
        mys_station = await _get_or_create(
            session, Unit, name="Devaraja PS", unit_type_id=station_type.id, district_id=mysuru.id
        )

        crime_head = await _get_or_create(session, CrimeHead, name="Theft", defaults={"code": "THEFT"})
        crime_sub_head = await _get_or_create(
            session, CrimeSubHead, crime_head_id=crime_head.id, name="Theft of motor vehicle"
        )
        gravity = await _get_or_create(session, GravityOffence, label="Non-Heinous", defaults={"chi_weight": 2.5})
        crime_sub_head.gravity_offence_id = gravity.id

        act = await _get_or_create(session, Act, name="Indian Penal Code", defaults={"short_name": "IPC"})
        section = await _get_or_create(session, Section, act_id=act.id, section_number="379", defaults={"description": "Theft"})
        case_status = await _get_or_create(session, CaseStatusMaster, status_name="Under Investigation")

        await _seed_users(session, bengaluru.id, blr_station.id)
        case, person_a, person_b, victim, document = await _seed_primary_case(
            session, blr_station.id, bengaluru.id, crime_head.id, crime_sub_head.id, gravity.id,
            case_status.id, act.id, section.id,
        )
        await _seed_secondary_case(session, mys_station.id, mysuru.id, crime_head.id, crime_sub_head.id, gravity.id, case_status.id)

        await session.commit()

        await _sync_to_graph(case, person_a, person_b, victim, document)

    log.info("Demo seed data loaded", demo_password=DEMO_PASSWORD, users=[u[0] for u in _DEMO_USERS])


async def _seed_users(session, bengaluru_district_id: int, blr_station_id: int) -> None:
    for email, full_name, role, badge in _DEMO_USERS:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            continue
        is_district_scoped = role in _DISTRICT_SCOPED_ROLES
        session.add(
            User(
                email=email,
                hashed_password=hash_password(DEMO_PASSWORD),
                full_name=full_name,
                role=role,
                badge_number=badge,
                district_id=bengaluru_district_id if is_district_scoped else None,
                unit_id=blr_station_id if is_district_scoped else None,
            )
        )
    await session.flush()


async def _seed_primary_case(
    session, unit_id, district_id, crime_head_id, crime_sub_head_id, gravity_id,
    case_status_id, act_id, section_id,
):
    existing = await session.execute(select(CaseMaster).where(CaseMaster.crime_no == "THEFT-BLR-INDR-2025-0142"))
    case = existing.scalar_one_or_none()
    if case is not None:
        role_rows = (await session.execute(
            select(PersonCaseRole).where(PersonCaseRole.case_id == case.id)
        )).scalars().all()
        accused_ids = [r.person_id for r in role_rows if r.role == PersonRole.ACCUSED]
        victim_ids = [r.person_id for r in role_rows if r.role == PersonRole.VICTIM]
        person_a = await session.get(Person, accused_ids[0])
        person_b = await session.get(Person, accused_ids[1]) if len(accused_ids) > 1 else person_a
        victim = await session.get(Person, victim_ids[0]) if victim_ids else person_a
        doc_result = await session.execute(select(Document).where(Document.linked_incident_id == case.id))
        document = doc_result.scalars().first()
        return case, person_a, person_b, victim, document

    person_a = Person(
        full_name="Manjunath Gowda", sex=Sex.MALE,
        permanent_address="12 MG Road, Bengaluru", present_address="12 MG Road, Bengaluru", human_verified=True,
    )
    person_b = Person(
        full_name="Naveen Reddy", sex=Sex.MALE,
        permanent_address="45 Brigade Road, Bengaluru", present_address="45 Brigade Road, Bengaluru", human_verified=True,
    )
    victim = Person(
        full_name="Ashwin Rao", sex=Sex.MALE,
        permanent_address="9 Church Street, Bengaluru", present_address="9 Church Street, Bengaluru", human_verified=True,
    )
    session.add_all([person_a, person_b, victim])
    await session.flush()

    case = CaseMaster(
        crime_no="THEFT-BLR-INDR-2025-0142",
        unit_id=unit_id,
        district_id=district_id,
        incident_from_date=date(2025, 3, 4),
        date_reported=date(2025, 3, 4),
        latitude=12.9716,
        longitude=77.6412,
        crime_head_id=crime_head_id,
        crime_sub_head_id=crime_sub_head_id,
        gravity_offence_id=gravity_id,
        case_status_id=case_status_id,
        brief_facts=(
            "Complainant reported that his motorcycle, parked outside his residence, was "
            "stolen overnight. Two suspects were seen on CCTV footage from a neighboring shop."
        ),
        source_type=SourceType.FIR,
    )
    session.add(case)
    await session.flush()

    session.add(ActSectionAssociation(case_id=case.id, act_id=act_id, section_id=section_id))
    session.add(CaseStageEvent(case_id=case.id, stage=CaseStage.REGISTERED, event_date=date(2025, 3, 4), confidence=1.0))
    session.add(CaseStageEvent(case_id=case.id, stage=CaseStage.INVESTIGATION, event_date=date(2025, 3, 6), confidence=1.0))

    session.add(PersonCaseRole(
        person_id=person_a.id, case_id=case.id, role=PersonRole.ACCUSED,
        arrested=True, arrest_date=date(2025, 3, 10), bail_granted=False,
    ))
    session.add(PersonCaseRole(person_id=person_b.id, case_id=case.id, role=PersonRole.ACCUSED, arrested=False))
    session.add(PersonCaseRole(person_id=victim.id, case_id=case.id, role=PersonRole.VICTIM))

    document = Document(
        source_type=SourceType.FIR, file_format=DocumentFormat.PDF, original_filename="fir_theft_blr_0142.pdf",
        raw_file_ref="seed://fir_theft_blr_0142.pdf", extraction_method=ExtractionMethod.TEMPLATE_EXTRACTION,
        confidence_score=0.92, linked_incident_id=case.id, human_verified=True,
    )
    session.add(document)

    # Shared, structuring-shaped financial link between the two accused —
    # exercises detect_structuring / the financial-crime graph on a fresh install.
    session.add(FinancialTransaction(
        from_account="ACCT-9931-2200-4821", to_account="ACCT-1187-5502-6634",
        amount=95000, transaction_date=date(2025, 3, 8), transaction_type="UPI",
        linked_person_id=person_a.id, linked_incident_id=case.id,
        alert_type=FinancialAlertType.STRUCTURING, alert_confidence=0.71,
        alert_details={"typology": "structuring", "threshold_inr": 1000000, "note": "seed demo data"},
    ))
    session.add(FinancialTransaction(
        from_account="ACCT-1187-5502-6634", to_account="ACCT-9931-2200-4821",
        amount=88000, transaction_date=date(2025, 3, 9), transaction_type="UPI",
        linked_person_id=person_b.id, linked_incident_id=case.id,
        alert_type=FinancialAlertType.STRUCTURING, alert_confidence=0.71,
        alert_details={"typology": "structuring", "threshold_inr": 1000000, "note": "seed demo data"},
    ))

    criminal_history = CriminalHistory(
        person_id=person_a.id, prior_incident_ids=[],
        mo_pattern_summary="Repeat vehicle theft reported in the same jurisdiction.", human_verified=True,
    )
    session.add(criminal_history)
    await session.flush()

    session.add(RiskScore(
        criminal_history_id=criminal_history.id, model_version="seed-v1", score=0.62,
        chi_weighted_harm=2.5, network_centrality=0.4, mo_escalation_score=0.3, associate_risk_avg=0.35,
        shap_decomposition={
            "chi_weighted_harm": 0.22, "network_centrality": 0.15,
            "mo_escalation_score": 0.1, "associate_risk_avg": 0.08,
        },
        human_reviewed=True,
    ))

    return case, person_a, person_b, victim, document


async def _seed_secondary_case(session, unit_id, district_id, crime_head_id, crime_sub_head_id, gravity_id, case_status_id) -> None:
    """A second case in a different district — exists purely so district-scoped
    RBAC (a Bengaluru constable/inspector) has something it should NOT see."""
    existing = await session.execute(select(CaseMaster).where(CaseMaster.crime_no == "THEFT-MYS-DEVJ-2025-0057"))
    if existing.scalar_one_or_none() is not None:
        return

    case = CaseMaster(
        crime_no="THEFT-MYS-DEVJ-2025-0057",
        unit_id=unit_id,
        district_id=district_id,
        incident_from_date=date(2025, 4, 1),
        date_reported=date(2025, 4, 1),
        crime_head_id=crime_head_id,
        crime_sub_head_id=crime_sub_head_id,
        gravity_offence_id=gravity_id,
        case_status_id=case_status_id,
        brief_facts="Shop burglary reported near Devaraja Market — investigation ongoing.",
        source_type=SourceType.FIR,
    )
    session.add(case)
    await session.flush()
    session.add(CaseStageEvent(case_id=case.id, stage=CaseStage.REGISTERED, event_date=date(2025, 4, 1), confidence=1.0))


async def _sync_to_graph(case, person_a, person_b, victim, document) -> None:
    graph_sync = GraphSyncService()
    await graph_sync.sync_document(
        {
            "case_id": str(case.id),
            "crime_no": case.crime_no,
            "date_reported": str(case.date_reported),
            "persons": [
                {"person_id": str(person_a.id), "full_name": person_a.full_name, "role": "accused", "aliases": []},
                {"person_id": str(person_b.id), "full_name": person_b.full_name, "role": "accused", "aliases": []},
                {"person_id": str(victim.id), "full_name": victim.full_name, "role": "victim", "aliases": []},
            ],
        },
        document,
    )
    await graph_sync.upsert_financial_edge(str(person_a.id), str(person_b.id), str(uuid.uuid4()), 95000)


if __name__ == "__main__":
    asyncio.run(seed())
