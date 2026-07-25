"""
Typology-driven synthetic FinancialTransaction seeder.

Fills the gap identified in the codebase: FinancialTransaction, FinancialCrimeService,
and the /financial/* endpoints all already exist, but nothing populates the table --
every detector was querying empty data. This script generates transactions the same
way AMLNet-style frameworks do: following real laundering typologies (structuring,
funnel/mule, layering), not random amounts between random accounts (design doc §9.1-9.2).

DROP-IN LOCATION: backend/scripts/seed_financial_transactions.py
RUN: python -m scripts.seed_financial_transactions   (from backend/, venv active,
     DATABASE_URL_ADMIN / NEO4J_URI pointing at running containers)

Uses the ADMIN (table-owning) connection, not AsyncSessionFactory -- same
reason seed_demo_data.py does: seeding is a bootstrap operation with no
logged-in user to derive app.current_role/district_id from, and the
case_master RLS policy (core/database.py::_setup_runtime_role_and_rls)
would silently return zero rows to the restricted app_runtime role instead
of raising, which would make _get_or_create_pool() below wrongly conclude
no CaseMaster rows exist and fall back to inventing its own -- confirmed
this is a real failure mode by reading seed_demo_data.py's own account of
hitting it first.

VIEW_FINANCIAL_RAW is only granted to DSP/SP/DGP/CRIME_ANALYST (core/permissions.py),
which is exactly the district-unrestricted role set in the RLS policy -- so the
NULL district_id on any fallback-created CaseMaster rows never actually hides
financial data from anyone who can see it in the first place.

Ground-truth typology labels are written to a local JSON file next to this script,
never into Postgres -- they exist only so validate_financial_crime.py can measure
precision/recall. They are not part of the handoff schema.
"""

import asyncio
import json
import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.graph_db import graph_db
from app.models.case import CaseMaster
from app.models.financial import FinancialTransaction
from app.models.person import Person
from app.models.enums import Sex
from app.models.unit import District, State

# Same 8 districts seed_demo_data.py already establishes (Karnataka/state
# code KA) -- reused by name so this pool lands on the *same* District rows
# if that script already ran, rather than creating a second parallel set.
_DISTRICT_NAMES = [
    ("Bengaluru Urban", "BLR"), ("Mysuru", "MYS"), ("Belagavi", "BGM"),
    ("Mangaluru", "MNR"), ("Kalaburagi", "KLB"), ("Hubballi-Dharwad", "HBL"),
    ("Shivamogga", "SMG"), ("Ballari", "BLI"),
]

# Real-sounding, varied Karnataka names -- not "Synthetic Person N". Mixed
# across common Kannada/Indian first and last names so 60 people don't read
# as an obviously generated list.
_FIRST_NAMES_MALE = [
    "Manjunath", "Naveen", "Ashwin", "Ravi", "Suresh", "Prakash", "Vijay",
    "Ganesh", "Harish", "Kiran", "Mahesh", "Nagaraj", "Raghavendra", "Santosh",
    "Shivaraj", "Sunil", "Umesh", "Vinod", "Yogesh", "Chandrashekar",
]
_FIRST_NAMES_FEMALE = [
    "Lakshmi", "Deepa", "Kavitha", "Manjula", "Nagaveni", "Pooja", "Radha",
    "Sandhya", "Shilpa", "Sowmya", "Sujatha", "Sunitha", "Usha", "Vani",
    "Vidya", "Anitha", "Bhagya", "Chaitra", "Gowri", "Jyothi",
]
_LAST_NAMES = [
    "Gowda", "Reddy", "Rao", "Naik", "Hegde", "Kulkarni", "Patil", "Shetty",
    "Iyengar", "Murthy", "Bhat", "Nayak", "Shenoy", "Deshpande", "Achar",
    "Poojary", "Kamath", "Prabhu", "Rai", "Acharya",
]

log = structlog.get_logger(__name__)

RNG_SEED = 42
GROUND_TRUTH_PATH = Path(__file__).parent / "financial_ground_truth.json"

# Same India-specific threshold used by FinancialCrimeService.
CTR_THRESHOLD_INR = 1_000_000.0


# ------------------------------------------------------------------ #
# Person / Case pool -- reuse real rows if they exist, else create a
# minimal synthetic pool so this script is runnable standalone before
# ingestion is finished.
# ------------------------------------------------------------------ #
async def _get_or_create_districts(session) -> list:
    """Reuses seed_demo_data.py's exact districts if that script already ran
    (matched by name), otherwise creates them -- either way ends up on real
    District rows, never a fake placeholder district."""
    result = await session.execute(select(State).filter_by(name="Karnataka"))
    state = result.scalar_one_or_none()
    if state is None:
        state = State(name="Karnataka", code="KA")
        session.add(state)
        await session.flush()

    districts = []
    for name, code in _DISTRICT_NAMES:
        result = await session.execute(select(District).filter_by(name=name))
        d = result.scalar_one_or_none()
        if d is None:
            d = District(name=name, state_id=state.id, code=code)
            session.add(d)
            await session.flush()
        districts.append(d)
    return districts


def _random_person_name(rng: random.Random) -> tuple:
    """Returns (full_name, sex) -- picking from the matching first-name pool
    so sex and name stay consistent, rather than generating one independent
    of the other."""
    if rng.random() < 0.5:
        first = rng.choice(_FIRST_NAMES_MALE)
        sex = Sex.MALE
    else:
        first = rng.choice(_FIRST_NAMES_FEMALE)
        sex = Sex.FEMALE
    last = rng.choice(_LAST_NAMES)
    return f"{first} {last}", sex


async def _get_or_create_pool(session, n_persons: int = 60, n_cases: int = 30, seed: int = RNG_SEED):
    """Ensures a pool of at least n_persons/n_cases, spread across all real
    Karnataka districts with varied demographics -- tops up rather than
    skipping entirely when a few rows already exist (e.g. from
    seed_demo_data.py's 2-3 named people), so bulk generation never ends up
    funneling 600+ transactions through a tiny, single-district pool."""
    rng = random.Random(seed)
    districts = await _get_or_create_districts(session)

    persons = (await session.execute(select(Person.id))).scalars().all()
    persons = list(persons)
    if len(persons) < n_persons:
        needed = n_persons - len(persons)
        log.info(f"Topping up person pool with {needed} demographically-varied rows across {len(districts)} districts")
        new_people = []
        for _ in range(needed):
            full_name, sex = _random_person_name(rng)
            district = rng.choice(districts)
            age = rng.randint(19, 64)
            person_kwargs = dict(
                full_name=full_name, sex=sex,
                date_of_birth=date(date.today().year - age, rng.randint(1, 12), rng.randint(1, 28)),
                age_at_registration=age,
                permanent_address=f"{rng.randint(1, 200)} Main Road, {district.name}",
                present_address=f"{rng.randint(1, 200)} Main Road, {district.name}",
            )
            if hasattr(Person, "is_synthetic"):
                person_kwargs["is_synthetic"] = True
            new_people.append(Person(**person_kwargs))
        session.add_all(new_people)
        await session.flush()
        persons.extend(p.id for p in new_people)

    cases = (await session.execute(select(CaseMaster.id))).scalars().all()
    cases = list(cases)
    if len(cases) < n_cases:
        needed = n_cases - len(cases)
        log.info(f"Topping up case pool with {needed} rows spread across {len(districts)} districts")
        new_cases = []
        for i in range(needed):
            district = rng.choice(districts)
            new_cases.append(
                CaseMaster(
                    crime_no=f"SYN/{district.code}/{uuid.uuid4().hex[:6].upper()}/2024",
                    district_id=district.id,
                    date_reported=date(2024, 1, 1) + timedelta(days=rng.randint(0, 300)),
                )
            )
        session.add_all(new_cases)
        await session.flush()
        cases.extend(c.id for c in new_cases)

    await session.commit()
    return persons, cases


def _account_id(prefix: str = "ACC") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


class TypologyGenerator:
    """Same typology logic as the standalone prototype (financial_crime/generate_transactions.py),
    adapted to use real Person/CaseMaster UUIDs instead of a placeholder pool."""

    def __init__(self, person_ids, case_ids, seed: int = RNG_SEED):
        self.rng = random.Random(seed)
        self.person_ids = person_ids
        self.case_ids = case_ids
        self.rows: list[dict] = []       # ORM-insertable dicts
        self.ground_truth: dict[str, str] = {}  # txn_id -> typology

    def _pick_person(self):
        return self.rng.choice(self.person_ids)

    def _pick_case(self):
        return self.rng.choice(self.case_ids)

    def _random_date(self, start: date, end: date) -> date:
        span = (end - start).days
        return start + timedelta(days=self.rng.randint(0, span))

    def _add(self, from_acc, to_acc, amount, txn_date, person_id, case_id, typology):
        txn_id = uuid.uuid4()
        self.rows.append(
            dict(
                id=txn_id,
                from_account=from_acc,
                to_account=to_acc,
                amount=round(amount, 2),
                currency="INR",
                transaction_date=txn_date,
                linked_person_id=person_id,
                linked_incident_id=case_id,
                is_synthetic=True,
            )
        )
        self.ground_truth[str(txn_id)] = typology

    def gen_structuring(self, n_cases: int = 10):
        for _ in range(n_cases):
            source, dest = _account_id(), _account_id()
            person, case = self._pick_person(), self._pick_case()
            start = self._random_date(date(2024, 1, 1), date(2024, 11, 1))

            target_total = self.rng.uniform(1_200_000, 4_000_000)
            leg_count = self.rng.randint(4, 9)
            remaining = target_total
            for i in range(leg_count):
                legs_left = leg_count - i
                max_leg = min(CTR_THRESHOLD_INR * 0.95, remaining - (legs_left - 1) * 50_000)
                amount = min(self.rng.uniform(max_leg * 0.6, max_leg), remaining)
                remaining -= amount
                self._add(
                    source, dest, amount,
                    start + timedelta(days=i * self.rng.randint(1, 3)),
                    person, case, "structuring",
                )

    def gen_funnel_account(self, n_cases: int = 10):
        for _ in range(n_cases):
            mule = _account_id()
            person, case = self._pick_person(), self._pick_case()
            spike_date = self._random_date(date(2024, 1, 1), date(2024, 10, 1))

            source_count = self.rng.randint(5, 15)
            total_in = 0.0
            for _ in range(source_count):
                source = _account_id()
                amount = self.rng.uniform(20_000, 400_000)
                total_in += amount
                self._add(
                    source, mule, amount,
                    spike_date + timedelta(hours=self.rng.randint(0, 48)),
                    person, case, "funnel",
                )

            withdrawal_dest = _account_id()
            self._add(
                mule, withdrawal_dest, total_in * self.rng.uniform(0.85, 0.98),
                spike_date + timedelta(days=self.rng.randint(1, 3)),
                person, case, "funnel",
            )

    def gen_layering_chain(self, n_cases: int = 10):
        for _ in range(n_cases):
            person, case = self._pick_person(), self._pick_case()
            chain_len = self.rng.randint(3, 6)
            accounts = [_account_id() for _ in range(chain_len)]
            if self.rng.random() < 0.4:
                accounts.append(accounts[0])  # loop back

            amount = self.rng.uniform(500_000, 3_000_000)
            start = self._random_date(date(2024, 1, 1), date(2024, 10, 1))

            for i in range(len(accounts) - 1):
                amount *= self.rng.uniform(0.92, 0.98)
                self._add(
                    accounts[i], accounts[i + 1], amount,
                    start + timedelta(days=i * self.rng.randint(2, 5)),
                    person, case, "layering",
                )

    def gen_clean_noise(self, n: int = 600):
        for _ in range(n):
            self._add(
                _account_id(), _account_id(),
                self.rng.uniform(500, 300_000),
                self._random_date(date(2024, 1, 1), date(2024, 12, 1)),
                self._pick_person(), self._pick_case(), "clean",
            )

    def generate_all(self):
        self.gen_structuring()
        self.gen_funnel_account()
        self.gen_layering_chain()
        self.gen_clean_noise()
        self.rng.shuffle(self.rows)
        return self.rows


async def _sync_to_neo4j(rows: list[dict]) -> None:
    """Writes two graph layers, and flags a real schema gap while doing it.

    ARCHITECTURE NOTE (worth raising with whoever owns graph_sync_service.py):
    FinancialTransaction carries exactly one linked_person_id per row -- there
    is no "who owns from_account" / "who owns to_account" pair, because there's
    no Account->Person ownership table. That means a true two-sided
    Person-TRANSACTED_WITH-Person edge (as GraphSyncService.upsert_financial_edge
    is shaped for) can't be derived from this data as-is -- there's only ever one
    known counterparty per transaction, not two.

    Two things are written instead, both honest given that constraint:
      1. Account-level graph (Account -[:TRANSACTED_WITH]-> Account) -- this is
         what structuring/funnel/layering are actually shapes IN (fan-out,
         fan-in/out, cycles are account-graph properties, not person-graph
         properties). detect_cycles_in_graph() below queries this layer.
      2. Person-level FINANCIALLY_ASSOCIATED_WITH edges, inferred when two
         different linked_person_id's transactions touch the same account --
         i.e. that shared account is the actual evidence connecting them.
         Kept as a distinct relationship name from TRANSACTED_WITH (which per
         graph_sync_service.py is reserved for a *confirmed* two-sided link)
         so this weaker, inferred evidence never gets silently conflated with
         a stronger confirmed edge type (design doc's own rule in §4: predicted
         links never merge with confirmed ones -- same principle applied here).
    """
    from collections import defaultdict
    from itertools import combinations

    await graph_db.connect()
    try:
        for row in rows:
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
                    "from_acc": row["from_account"],
                    "to_acc": row["to_account"],
                    "txn_id": str(row["id"]),
                    "amount": float(row["amount"]),
                    "date": str(row["transaction_date"]),
                    "pid": str(row["linked_person_id"]),
                    "cid": str(row["linked_incident_id"]),
                },
            )

        account_to_persons: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            pid = str(row["linked_person_id"])
            account_to_persons[row["from_account"]].add(pid)
            account_to_persons[row["to_account"]].add(pid)

        for account, people in account_to_persons.items():
            if len(people) < 2:
                continue
            for p1, p2 in combinations(sorted(people), 2):
                await graph_db.execute_query(
                    """
                    MERGE (a:Person {id: $p1})
                    MERGE (b:Person {id: $p2})
                    MERGE (a)-[r:FINANCIALLY_ASSOCIATED_WITH]-(b)
                    SET r.shared_account = $account, r.evidence_type = 'financial',
                        r.updated_at = datetime()
                    """,
                    {"p1": p1, "p2": p2, "account": account},
                )
    finally:
        await graph_db.close()


async def seed() -> None:
    admin_engine = create_async_engine(settings.DATABASE_URL_ADMIN, pool_pre_ping=True)
    admin_session_factory = async_sessionmaker(
        admin_engine, expire_on_commit=False, autocommit=False, autoflush=False
    )
    try:
        async with admin_session_factory() as session:
            person_ids, case_ids = await _get_or_create_pool(session)

            gen = TypologyGenerator(person_ids, case_ids)
            rows = gen.generate_all()

            session.add_all([FinancialTransaction(**row) for row in rows])
            await session.commit()
            log.info("Inserted synthetic FinancialTransaction rows", count=len(rows))
    finally:
        await admin_engine.dispose()

    GROUND_TRUTH_PATH.write_text(json.dumps(gen.ground_truth, indent=2))
    log.info("Ground truth written", path=str(GROUND_TRUTH_PATH), count=len(gen.ground_truth))

    await _sync_to_neo4j(rows)
    log.info("Synced Person nodes + TRANSACTED_WITH edges to Neo4j")


if __name__ == "__main__":
    asyncio.run(seed())
