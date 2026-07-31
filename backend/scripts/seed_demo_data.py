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

Runs through the admin (table-owning) connection, not the RLS-restricted
app_runtime role AsyncSessionFactory normally uses — seeding is a bootstrap
operation with no logged-in user to derive app.current_role/district_id from,
and the district-isolation RLS policies correctly deny every insert otherwise
(confirmed by hitting exactly that failure while first testing this script).
"""

import asyncio
import os
import uuid
from datetime import date, time, timedelta

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import init_db
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
from app.models.socio import CrimeStatAggregate, SocioEconomicIndicator
from app.models.unit import District, State, Unit, UnitType
from app.models.user import User
from app.core.graph_db import graph_db
from app.services.graph_sync_service import GraphSyncService
from app.services.analytics.gwr import compute_all_districts_gwr

log = structlog.get_logger(__name__)

# Overridable via env rather than baked in — a hackathon demo still shouldn't
# ship with a password no one can change without editing source. The fallback
# values only apply when the corresponding env var is unset, so a real
# deployment can override every one of these without touching this file.
DEMO_PASSWORD = os.environ.get("SEED_DEMO_PASSWORD", "Demo@12345")
ADMIN_EMAIL = os.environ.get("SEED_ADMIN_EMAIL", "admin@ksp.demo")
ADMIN_PASSWORD = os.environ.get("SEED_ADMIN_PASSWORD", DEMO_PASSWORD)

_DEMO_USERS = [
    ("dgp@ksp.demo", "Rajendra Holla", Role.DGP, "DGP-0001"),
    ("sp@ksp.demo", "Meera Nayak", Role.SP, "SP-0007"),
    ("dsp@ksp.demo", "Arvind Kulkarni", Role.DSP, "DSP-0021"),
    ("inspector@ksp.demo", "Suresh Patil", Role.INSPECTOR, "INS-0134"),
    ("constable@ksp.demo", "Ravi Kumar", Role.CONSTABLE, "PC-4471"),
    ("analyst@ksp.demo", "Divya Shenoy", Role.CRIME_ANALYST, "CA-0009"),
    ("policymaker@ksp.demo", "Anil Deshpande", Role.POLICY_MAKER, "PM-0002"),
]

# A dedicated System Administrator account, distinct from the police-officer
# demo personas above — DGP-tier permissions (the only rank with manage_users),
# but seeded separately so "who can administer the platform" isn't tangled up
# with "who plays the DGP character in the demo." Its own env-overridable
# credentials, kept out of _DEMO_USERS so it's never confused with a rank login.
ADMIN_USER = (ADMIN_EMAIL, "System Administrator", Role.DGP, "ADMIN-0001")

# Ranks tied to a posting — mirrors CaseRepository._DISTRICT_UNRESTRICTED_ROLES.
_DISTRICT_SCOPED_ROLES = {Role.CONSTABLE, Role.INSPECTOR}

# Every seeded date is relative to today, not a fixed calendar date — the
# financial-crime detection endpoints (detect_structuring et al.) only look
# back a bounded window (default 30 days, max 90), so fixed historical dates
# would silently stop demonstrating anything the moment enough real time
# passed (caught exactly this way while first verifying this script live).
_TODAY = date.today()


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
    # init_db() only opens Postgres connections — this script runs standalone,
    # outside the FastAPI app's lifespan, so the Neo4j pool graph_sync needs
    # below has never been established either.
    await graph_db.connect()

    admin_engine = create_async_engine(settings.DATABASE_URL_ADMIN, pool_pre_ping=True)
    admin_session_factory = async_sessionmaker(
        admin_engine, expire_on_commit=False, autocommit=False, autoflush=False
    )

    async with admin_session_factory() as session:
        state = await _get_or_create(session, State, name="Karnataka", defaults={"code": "KA"})
        
        districts_data = [
            ("Bengaluru Urban", "BLR", 88.7, 7.2, 90.5, 954.0, 0.68),
            ("Mysuru", "MYS", 82.3, 5.8, 41.5, 982.0, 0.42),
            ("Belagavi", "BGM", 73.5, 6.4, 25.3, 970.0, 0.58),
            ("Mangaluru", "MNR", 88.9, 4.9, 47.6, 1020.0, 0.35),
            ("Kalaburagi", "KLB", 65.2, 8.1, 32.7, 971.0, 0.72),
            ("Hubballi-Dharwad", "HBL", 80.1, 6.9, 58.2, 968.0, 0.54),
            ("Shivamogga", "SMG", 80.5, 5.2, 35.6, 995.0, 0.40),
            ("Ballari", "BLI", 67.4, 7.8, 37.5, 983.0, 0.65),
        ]
        district_objs = {}
        for name, code, lit, unemp, urb, sex, stress in districts_data:
            d = await _get_or_create(session, District, name=name, state_id=state.id, defaults={"code": code})
            district_objs[name] = d
            for yr in range(2021, 2026):
                await _get_or_create(
                    session,
                    SocioEconomicIndicator,
                    district_id=d.id,
                    year=yr,
                    defaults={
                        "literacy_rate": round(lit + (yr - 2021) * 0.4, 2),
                        "unemployment_rate": round(max(2.0, unemp + (yr - 2021) * 0.2), 2),
                        "urbanization_pct": round(urb + (yr - 2021) * 0.8, 2),
                        "population_density": 450.0,
                        "sex_ratio": sex,
                        "composite_stress_index": stress,
                    },
                )

        bengaluru = district_objs["Bengaluru Urban"]
        mysuru = district_objs["Mysuru"]

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

        # Seed CrimeStatAggregate per district per year
        for d_name, d_obj in district_objs.items():
            base_count = 150 if "Bengaluru" in d_name else (90 if "Hubballi" in d_name or "Mangaluru" in d_name else 60)
            for yr in range(2021, 2026):
                await _get_or_create(
                    session,
                    CrimeStatAggregate,
                    district_id=d_obj.id,
                    year=yr,
                    crime_head_id=crime_head.id,
                    defaults={
                        "count": base_count + (yr - 2021) * 12,
                        "chi_weighted_count": (base_count + (yr - 2021) * 12) * 2.2,
                    },
                )

        await _seed_users(session, bengaluru.id, blr_station.id)
        case, person_a, person_b, victim, document = await _seed_primary_case(
            session, blr_station.id, bengaluru.id, crime_head.id, crime_sub_head.id, gravity.id,
            case_status.id, act.id, section.id,
        )
        await _seed_secondary_case(session, mys_station.id, mysuru.id, crime_head.id, crime_sub_head.id, gravity.id, case_status.id)

        await session.commit()
        await _sync_to_graph(session, case, person_a, person_b, victim, document)

        # Trigger GWR run so coefficients exist in DB
        try:
            await compute_all_districts_gwr(session)
        except Exception as err:
            log.warning("GWR computation during seed skipped or failed", error=str(err))


    await admin_engine.dispose()
    await graph_db.close()
    log.info(
        "Demo seed data loaded",
        demo_password=DEMO_PASSWORD,
        rank_demo_users=[u[0] for u in _DEMO_USERS],
        admin_user=ADMIN_EMAIL,
        admin_password=ADMIN_PASSWORD,
    )


async def _seed_users(session, bengaluru_district_id: int, blr_station_id: int) -> None:
    for email, full_name, role, badge in [*_DEMO_USERS, ADMIN_USER]:
        existing = await session.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            continue
        is_district_scoped = role in _DISTRICT_SCOPED_ROLES
        password = ADMIN_PASSWORD if email == ADMIN_EMAIL else DEMO_PASSWORD
        session.add(
            User(
                email=email,
                hashed_password=hash_password(password),
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
        full_name="Manjunath Gowda", sex=Sex.MALE, date_of_birth=date(_TODAY.year - 28, 6, 15),
        permanent_address="12 MG Road, Bengaluru", present_address="12 MG Road, Bengaluru", human_verified=True,
    )
    person_b = Person(
        full_name="Naveen Reddy", sex=Sex.MALE, date_of_birth=date(_TODAY.year - 34, 3, 22),
        permanent_address="45 Brigade Road, Bengaluru", present_address="45 Brigade Road, Bengaluru", human_verified=True,
    )
    victim = Person(
        full_name="Ashwin Rao", sex=Sex.MALE, date_of_birth=date(_TODAY.year - 52, 11, 3),
        permanent_address="9 Church Street, Bengaluru", present_address="9 Church Street, Bengaluru", human_verified=True,
    )
    session.add_all([person_a, person_b, victim])
    await session.flush()

    case = CaseMaster(
        crime_no="THEFT-BLR-INDR-2025-0142",
        unit_id=unit_id,
        district_id=district_id,
        incident_from_date=_TODAY - timedelta(days=14),
        date_reported=_TODAY - timedelta(days=14),
        incident_time=time(23, 15),
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
    session.add(CaseStageEvent(case_id=case.id, stage=CaseStage.REGISTERED, event_date=_TODAY - timedelta(days=14), confidence=1.0))
    session.add(CaseStageEvent(case_id=case.id, stage=CaseStage.INVESTIGATION, event_date=_TODAY - timedelta(days=12), confidence=1.0))

    session.add(PersonCaseRole(
        person_id=person_a.id, case_id=case.id, role=PersonRole.ACCUSED,
        arrested=True, arrest_date=_TODAY - timedelta(days=8), bail_granted=False,
    ))
    session.add(PersonCaseRole(person_id=person_b.id, case_id=case.id, role=PersonRole.ACCUSED, arrested=False))
    session.add(PersonCaseRole(person_id=victim.id, case_id=case.id, role=PersonRole.VICTIM))

    document = Document(
        source_type=SourceType.FIR, file_format=DocumentFormat.PDF, original_filename="fir_theft_blr_0142.pdf",
        raw_file_ref="seed://fir_theft_blr_0142.pdf", extraction_method=ExtractionMethod.TEMPLATE_EXTRACTION,
        confidence_score=0.92, linked_incident_id=case.id, human_verified=True,
    )
    session.add(document)

    # A real structuring pattern between the two accused — four transfers, each
    # individually under India's real ₹10 lakh (1,000,000) cash-transaction
    # reporting threshold, but summing to more than it once grouped by
    # destination account (exactly what detect_structuring's SQL groups on).
    # A single transaction (the original version of this seed data) can never
    # trigger that query regardless of date — structuring is inherently a
    # multi-transaction shape, not a property of any one row.
    structuring_transfers = [
        (280_000, 13), (260_000, 11), (290_000, 9), (240_000, 7),
    ]
    for amount, days_ago in structuring_transfers:
        session.add(FinancialTransaction(
            from_account="ACCT-9931-2200-4821", to_account="ACCT-1187-5502-6634",
            amount=amount, transaction_date=_TODAY - timedelta(days=days_ago), transaction_type="UPI",
            linked_person_id=person_a.id, linked_incident_id=case.id,
            alert_type=FinancialAlertType.STRUCTURING, alert_confidence=0.71,
            alert_details={"typology": "structuring", "threshold_inr": 1_000_000, "note": "seed demo data"},
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

    # A funnel/mule pattern on person_b's own account — five distinct source
    # accounts feed in within a 2-day window (funnel's fan-in), no prior
    # activity on the mule account in the 60 days before that (the dormancy
    # check detect_funnel_account requires), then ~90% of it leaves again
    # within days (the rapid-emptying half of the pattern).
    mule_account = "ACCT-4471-0093-7712"
    funnel_sources = [
        "ACCT-2200-1183-9014", "ACCT-3391-4402-1187", "ACCT-5512-2200-3398",
        "ACCT-6603-3311-4409", "ACCT-7714-4422-5510",
    ]
    funnel_inflow_date = _TODAY - timedelta(days=6)
    total_in = 0
    for i, source in enumerate(funnel_sources):
        amount = 180_000 + i * 15_000
        total_in += amount
        session.add(FinancialTransaction(
            from_account=source, to_account=mule_account,
            amount=amount, transaction_date=funnel_inflow_date + timedelta(hours=i * 4), transaction_type="NEFT",
            linked_person_id=person_b.id, linked_incident_id=case.id,
            alert_type=FinancialAlertType.FUNNEL_ACCOUNT, alert_confidence=0.68,
            alert_details={"typology": "funnel", "role": "inflow", "note": "seed demo data"},
        ))
    session.add(FinancialTransaction(
        from_account=mule_account, to_account="ACCT-8825-5533-6621",
        amount=round(total_in * 0.9), transaction_date=funnel_inflow_date + timedelta(days=1), transaction_type="IMPS",
        linked_person_id=person_b.id, linked_incident_id=case.id,
        alert_type=FinancialAlertType.FUNNEL_ACCOUNT, alert_confidence=0.68,
        alert_details={"typology": "funnel", "role": "withdrawal", "note": "seed demo data"},
    ))

    # A layering chain also tied to person_b — money hops through three
    # intermediary accounts, shrinking slightly each hop, over several days,
    # then loops back to its origin. detect_cycles_in_graph specifically
    # requires a closed loop (MATCH path = (a)-[:TRANSACTED_WITH*2..]->(a)) --
    # a linear, non-looping chain would never be found by it, so the last
    # hop deliberately returns to layering_chain[0].
    layering_chain = [
        "ACCT-1001-2002-3003", "ACCT-2002-3003-4004",
        "ACCT-3003-4004-5005", "ACCT-4004-5005-6006",
        "ACCT-1001-2002-3003",  # loop back to origin
    ]
    layering_start = _TODAY - timedelta(days=20)
    layering_amount = 1_800_000
    for i in range(len(layering_chain) - 1):
        layering_amount = round(layering_amount * 0.95)
        session.add(FinancialTransaction(
            from_account=layering_chain[i], to_account=layering_chain[i + 1],
            amount=layering_amount, transaction_date=layering_start + timedelta(days=i * 3), transaction_type="RTGS",
            linked_person_id=person_b.id, linked_incident_id=case.id,
            alert_type=FinancialAlertType.LAYERING, alert_confidence=0.65,
            alert_details={"typology": "layering", "hop": i + 1, "note": "seed demo data"},
        ))

    criminal_history_b = CriminalHistory(
        person_id=person_b.id, prior_incident_ids=[],
        mo_pattern_summary="Named in two financial-crime patterns (funnel account, layering) alongside the vehicle theft case.",
        human_verified=True,
    )
    session.add(criminal_history_b)
    await session.flush()

    # Higher associate_risk_avg than person_a — this reflects the design
    # doc's rule that a confirmed FinancialTransaction.linked_person_id is
    # direct case evidence, not ecological/demographic inference, so it's
    # allowed to strengthen this specific feature (§9.4/§7.4).
    session.add(RiskScore(
        criminal_history_id=criminal_history_b.id, model_version="seed-v1", score=0.71,
        chi_weighted_harm=2.0, network_centrality=0.35, mo_escalation_score=0.25, associate_risk_avg=0.55,
        shap_decomposition={
            "chi_weighted_harm": 0.16, "network_centrality": 0.12,
            "mo_escalation_score": 0.08, "associate_risk_avg": 0.20,
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
        incident_from_date=_TODAY - timedelta(days=5),
        date_reported=_TODAY - timedelta(days=5),
        incident_time=time(2, 40),
        crime_head_id=crime_head_id,
        crime_sub_head_id=crime_sub_head_id,
        gravity_offence_id=gravity_id,
        case_status_id=case_status_id,
        brief_facts="Shop burglary reported near Devaraja Market — investigation ongoing.",
        source_type=SourceType.FIR,
    )
    session.add(case)
    await session.flush()
    session.add(CaseStageEvent(case_id=case.id, stage=CaseStage.REGISTERED, event_date=_TODAY - timedelta(days=5), confidence=1.0))

    # A second victim in a different age cohort/gender — otherwise the real
    # victim-demographics computation (socio_insights.get_victim_demographics)
    # has exactly one data point statewide, which is technically correct but
    # not demonstrable as a real cohort breakdown.
    victim2 = Person(
        full_name="Lakshmi Devi", sex=Sex.FEMALE, date_of_birth=date(_TODAY.year - 63, 8, 9),
        permanent_address="Devaraja Market Road, Mysuru", present_address="Devaraja Market Road, Mysuru",
        human_verified=True,
    )
    session.add(victim2)
    await session.flush()
    session.add(PersonCaseRole(person_id=victim2.id, case_id=case.id, role=PersonRole.VICTIM))


async def _sync_to_graph(session, case, person_a, person_b, victim, document) -> None:
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

    # Push every FinancialTransaction on this case into Neo4j as an
    # Account-level TRANSACTED_WITH graph -- detect_cycles_in_graph and
    # detect_organized_clusters both query Account nodes there (see
    # financial_crime.py), and nothing else in this script writes that graph.
    # Without this, the structuring/funnel/layering demo rows above sit in
    # Postgres just fine but stay invisible to the two Neo4j-backed detectors.
    txns = (
        await session.execute(select(FinancialTransaction).where(FinancialTransaction.linked_incident_id == case.id))
    ).scalars().all()
    for txn in txns:
        await graph_db.execute_query(
            """
            MERGE (a:Account {account_no: $from_acc})
            MERGE (b:Account {account_no: $to_acc})
            MERGE (a)-[r:TRANSACTED_WITH {transaction_id: $txn_id}]->(b)
            SET r.amount = $amount, r.date = $date,
                r.linked_person_id = $pid, r.linked_incident_id = $cid,
                r.updated_at = datetime()
            """,
            {
                "from_acc": txn.from_account, "to_acc": txn.to_account,
                "txn_id": str(txn.id), "amount": float(txn.amount), "date": str(txn.transaction_date),
                "pid": str(txn.linked_person_id), "cid": str(txn.linked_incident_id),
            },
        )
        if txn.linked_person_id:
            await graph_db.execute_query(
                """
                MERGE (p:Person {id: $pid})
                MERGE (a:Account {account_no: $from_acc})
                MERGE (b:Account {account_no: $to_acc})
                MERGE (p)-[:HAS_ACCOUNT]->(a)
                MERGE (p)-[:HAS_ACCOUNT]->(b)
                """,
                {
                    "pid": str(txn.linked_person_id),
                    "from_acc": txn.from_account,
                    "to_acc": txn.to_account,
                },
            )

    # Seed predicted links in Neo4j for demo suspects
    print("Seeding PREDICTED_LINK relationships in Neo4j...")
    await graph_db.execute_query(
        """
        MERGE (a:Person {id: $a_id})
        MERGE (b:Person {id: $b_id})
        MERGE (a)-[r:PREDICTED_LINK]-(b)
        SET r.confidence = 0.85,
            r.model_version = 'GCN-LinkPredict-v2',
            r.source_tool = 'Co-Offending & Structured Transfer Linker',
            r.evidence = 'Shared IP logins and common structured cash recipients within 48h',
            r.updated_at = datetime()
        """,
        {"a_id": str(person_a.id), "b_id": str(person_b.id)},
    )
    await graph_db.execute_query(
        """
        MERGE (a:Person {id: $a_id})
        MERGE (b:Person {id: $b_id})
        MERGE (a)-[r:PREDICTED_LINK]-(b)
        SET r.confidence = 0.62,
            r.model_version = 'Spatial-LinkPredict-v2',
            r.source_tool = 'Spatial Co-location Model',
            r.evidence = 'Co-located at 3 crime scene grids during incident times',
            r.updated_at = datetime()
        """,
        {"a_id": str(person_b.id), "b_id": str(victim.id)},
    )


if __name__ == "__main__":
    asyncio.run(seed())
