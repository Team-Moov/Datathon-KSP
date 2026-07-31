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
from datetime import date, timedelta, time
from pathlib import Path

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.district_coords import DEFAULT_DISTRICT_COORDS
from app.core.graph_db import graph_db
from app.models.case import CaseMaster, CrimeHead, CrimeSubHead, GravityOffence
from app.models.financial import FinancialTransaction
from app.models.person import Person
from app.models.enums import PersonRole, Sex
from app.models.person import PersonCaseRole
from app.models.socio import CrimeStatAggregate
from app.models.unit import District, State, Unit, UnitType
from app.models.offender import CriminalHistory, RiskScore

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

# Every generated date is relative to TODAY, never a fixed calendar year.
# seed_demo_data.py established this rule for the same reason and documents it:
# the detection/forecast endpoints only look back a bounded window
# (HawkesETASService._compute_intensity discards anything more than 30 days
# before the target date, and the Trends page defaults that target to today),
# so hardcoded 2024 dates silently produce "100% chronic / 0% acute" and an
# empty near-repeat layer forever. Confirmed live: the same forecast returned
# 0% acute for a 2026 target and non-zero acute for a 2024-11 target.
_TODAY = date.today()
_WINDOW_DAYS = 180


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


async def _get_or_create_units(session, districts) -> dict:
    """Two police stations per district. Needed for two separate reasons:
    CaseMaster.unit_id is what the multi-jurisdiction repeat-offender detector
    keys off (NetworkAnalysisService.get_multi_jurisdiction_offenders collects
    DISTINCT i.unit_id per person), and the real KSP schema's Unit hierarchy
    is what makes "this offender's cases span multiple jurisdictions" a
    meaningful organized/mobile-activity signal at all. With every case
    sharing one NULL unit_id, that detector can never fire."""
    result = await session.execute(select(UnitType).filter_by(name="Police Station"))
    station_type = result.scalar_one_or_none()
    if station_type is None:
        station_type = UnitType(name="Police Station", hierarchy_level=3)
        session.add(station_type)
        await session.flush()

    units_by_district: dict = {}
    for district in districts:
        existing = (
            await session.execute(select(Unit).where(Unit.district_id == district.id))
        ).scalars().all()
        units = list(existing)
        for idx in range(len(units), 2):
            unit = Unit(
                name=f"{district.name} Financial Crimes PS-{idx + 1}",
                unit_type_id=station_type.id,
                district_id=district.id,
            )
            session.add(unit)
            await session.flush()
            units.append(unit)
        units_by_district[district.id] = units
    return units_by_district


async def _link_accused(session, new_cases, person_ids, rng) -> None:
    """Attach 2-3 accused per case via PersonCaseRole.

    This is what actually creates a co-offending graph: two people accused in
    the SAME case become an edge, which is what
    NetworkAnalysisService.detect_communities() (organized-group alerts) and
    the repeat-offender detector both traverse. Without these rows the
    financial cases exist but have no people attached to them at all, so
    Early-Warning could only ever produce FINANCIAL alerts and never
    ORGANIZED_GROUP / REPEAT_OFFENDER ones -- confirmed live before this fix.

    Draws each case's accused from a small rotating "crew" pool rather than
    uniformly at random, because uniform sampling over 60 people produces a
    sparse graph with no community structure for Louvain to find, and no
    person accumulating cases across enough jurisdictions to look like a
    repeat offender.
    """
    if not person_ids:
        return

    crew_size = 6
    crews = [person_ids[i:i + crew_size] for i in range(0, len(person_ids), crew_size)]
    crews = [c for c in crews if len(c) >= 3]
    if not crews:
        crews = [person_ids]

    rows = []
    for idx, case in enumerate(new_cases):
        crew = crews[idx % len(crews)]
        accused = rng.sample(crew, min(len(crew), rng.randint(2, 3)))
        for person_id in accused:
            rows.append(
                PersonCaseRole(
                    person_id=person_id,
                    case_id=case.id,
                    role=PersonRole.ACCUSED,
                    arrested=rng.random() < 0.3,
                )
            )

        # One victim per case, drawn from OUTSIDE the offending crew.
        # Needed for SocioInsightsService.get_victim_demographics(), which is
        # how financial crime reaches the Sociological Insights tab at all:
        # it buckets by CrimeHead name, and "Financial Crime" matches its
        # "financial" keyword into the "Cyber & Financial Fraud" category --
        # but it only counts PersonCaseRole rows with role=VICTIM, so an
        # accused-only case contributes nothing there.
        victim_pool = [p for p in person_ids if p not in crew]
        if victim_pool:
            rows.append(
                PersonCaseRole(
                    person_id=rng.choice(victim_pool),
                    case_id=case.id,
                    role=PersonRole.VICTIM,
                )
            )

    session.add_all(rows)
    await session.flush()
    log.info(f"Linked {len(rows)} accused/victim role rows across {len(new_cases)} cases (co-offending + demographics)")


async def _seed_background_crime(session, districts, units_by_district, person_ids, rng) -> list:
    """Non-financial cases so financial crime is a plausible minority.

    Weighted roughly toward property offences, which dominate real NCRB
    counts, with economic offences a much smaller slice. Each case gets a
    victim so victim-demographic breakdowns have something other than
    financial crime to report.
    """
    # (crime head, sub head, gravity label, chi weight, cases per district)
    spec = [
        ("Theft", "Theft of motor vehicle", "Non-Heinous", 2.5, 22),
        ("Burglary", "House breaking by night", "Non-Heinous", 3.0, 14),
        ("Assault", "Voluntarily causing hurt", "Heinous", 5.0, 9),
        ("Cheating", "Cheating and dishonestly inducing delivery of property", "Non-Heinous", 2.0, 11),
    ]

    created: list = []
    for head_name, sub_name, gravity_label, chi_weight, per_district in spec:
        result = await session.execute(select(GravityOffence).filter_by(label=gravity_label))
        gravity = result.scalar_one_or_none()
        if gravity is None:
            gravity = GravityOffence(label=gravity_label, chi_weight=chi_weight)
            session.add(gravity)
            await session.flush()

        result = await session.execute(select(CrimeHead).filter_by(name=head_name))
        head = result.scalar_one_or_none()
        if head is None:
            head = CrimeHead(name=head_name)
            session.add(head)
            await session.flush()

        result = await session.execute(
            select(CrimeSubHead).filter_by(crime_head_id=head.id, name=sub_name)
        )
        sub_head = result.scalar_one_or_none()
        if sub_head is None:
            sub_head = CrimeSubHead(
                crime_head_id=head.id, name=sub_name, gravity_offence_id=gravity.id
            )
            session.add(sub_head)
            await session.flush()

        existing = dict(
            (
                await session.execute(
                    select(CaseMaster.district_id, func.count())
                    .where(CaseMaster.crime_head_id == head.id)
                    .group_by(CaseMaster.district_id)
                )
            ).all()
        )

        batch = []
        counts_by_district_year: dict = {}
        for district in districts:
            needed = max(0, per_district - existing.get(district.id, 0))
            base_lat, base_lon = DEFAULT_DISTRICT_COORDS.get(district.name, (12.9716, 77.5946))
            for _ in range(needed):
                report_date = _TODAY - timedelta(days=rng.randint(0, _WINDOW_DAYS))
                batch.append(
                    CaseMaster(
                        crime_no=f"SYN/{district.code}/{uuid.uuid4().hex[:6].upper()}/{_TODAY.year}",
                        district_id=district.id,
                        unit_id=rng.choice(units_by_district[district.id]).id,
                        crime_head_id=head.id,
                        crime_sub_head_id=sub_head.id,
                        gravity_offence_id=gravity.id,
                        date_reported=report_date,
                        incident_from_date=report_date,
                        incident_time=time(rng.randint(0, 23), rng.choice([0, 15, 30, 45])),
                        latitude=round(base_lat + rng.uniform(-0.12, 0.12), 6),
                        longitude=round(base_lon + rng.uniform(-0.12, 0.12), 6),
                        brief_facts=f"Synthetic {head_name.lower()} case providing realistic background crime volume.",
                    )
                )
                key = (district.id, report_date.year)
                counts_by_district_year[key] = counts_by_district_year.get(key, 0) + 1

        if not batch:
            continue

        session.add_all(batch)
        await session.flush()
        created.extend(batch)

        # One accused + one victim per background case, so these cases also
        # populate victim demographics rather than only inflating raw counts.
        roles = []
        for case in batch:
            roles.append(PersonCaseRole(
                person_id=rng.choice(person_ids), case_id=case.id, role=PersonRole.ACCUSED
            ))
            roles.append(PersonCaseRole(
                person_id=rng.choice(person_ids), case_id=case.id, role=PersonRole.VICTIM
            ))
        session.add_all(roles)

        for (district_id, year), count in counts_by_district_year.items():
            existing_agg = await session.execute(
                select(CrimeStatAggregate).filter_by(
                    district_id=district_id, year=year, crime_head_id=head.id
                )
            )
            row = existing_agg.scalar_one_or_none()
            if row is None:
                session.add(CrimeStatAggregate(
                    district_id=district_id, year=year, crime_head_id=head.id,
                    count=count, chi_weighted_count=count * float(chi_weight),
                ))
            else:
                row.count += count
                row.chi_weighted_count = (row.chi_weighted_count or 0) + count * float(chi_weight)

    await session.flush()
    if created:
        log.info(f"Created {len(created)} background (non-financial) cases so financial crime is a realistic minority")
    return created


async def _get_or_create_financial_crime_head(session) -> tuple:
    """A real CrimeHead/CrimeSubHead/GravityOffence for financial crime, not a
    NULL category. Without this, financial cases are invisible to every
    feature that reads CaseMaster.crime_head_id: temporal trends, Hawkes
    forecasting, the socio-insights victim-demographics classifier (which
    already has a "financial"-keyword bucket in _crime_bucket(), but only
    fires if a crime_head name actually contains that word), and
    CrimeStatAggregate-based correlation. Named "Financial Crime" specifically
    so that keyword match hits.
    """
    result = await session.execute(select(GravityOffence).filter_by(label="Heinous"))
    gravity = result.scalar_one_or_none()
    if gravity is None:
        gravity = GravityOffence(label="Heinous", chi_weight=4.0)
        session.add(gravity)
        await session.flush()

    result = await session.execute(select(CrimeHead).filter_by(name="Financial Crime"))
    head = result.scalar_one_or_none()
    if head is None:
        head = CrimeHead(name="Financial Crime", code="FINCRIME")
        session.add(head)
        await session.flush()

    result = await session.execute(
        select(CrimeSubHead).filter_by(crime_head_id=head.id, name="Money Laundering / Suspicious Transactions")
    )
    sub_head = result.scalar_one_or_none()
    if sub_head is None:
        sub_head = CrimeSubHead(
            crime_head_id=head.id,
            name="Money Laundering / Suspicious Transactions",
            gravity_offence_id=gravity.id,
        )
        session.add(sub_head)
        await session.flush()

    return head, sub_head


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


async def _get_or_create_pool(session, n_persons: int = 60, n_cases: int = 30, per_district_cases: int = 24, seed: int = RNG_SEED):
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

        mo_summaries = [
            "Intercepts transit delivery trucks by tailgating in high-density traffic corridors.",
            "Uses spoofed caller-ID numbers pretending to be bank agents to extract OTP credentials.",
            "Deposits structural cash sums below mandatory reporting limits across multiple bank branches.",
            "Unlocks parked light commercial trucks using custom keys in industrial zones.",
            "Procures bank account details from local day-laborers to route suspicious UPI wire payments.",
            "Breaks locks of residential properties during early morning hours to steal household valuables.",
            "Uses fraudulent digital billing accounts to divert merchant credit payouts.",
            "Launches malicious social engineering attacks targeting elder trust accounts via remote-access apps.",
            "Enters locked commercial complexes using crowbars on back doors to dismantle cash registers.",
            "Recruits local youths as money mules to funnel illegal betting returns to offshore destinations."
        ]
        for p in new_people:
            mo_pattern = rng.choice(mo_summaries)
            hist = CriminalHistory(
                person_id=p.id,
                prior_incident_ids=[],
                mo_pattern_summary=mo_pattern,
                human_verified=True,
            )
            session.add(hist)
            await session.flush()
            
            score_val = round(rng.uniform(0.15, 0.85), 2)
            session.add(RiskScore(
                criminal_history_id=hist.id,
                model_version="seed-v1",
                score=score_val,
                chi_weighted_harm=round(rng.uniform(1.0, 6.0), 1),
                network_centrality=round(rng.uniform(0.05, 0.9), 2),
                mo_escalation_score=round(rng.uniform(0.1, 0.8), 2),
                associate_risk_avg=round(rng.uniform(0.1, 0.8), 2),
                shap_decomposition={
                    "chi_weighted_harm": round(score_val * 0.4, 2),
                    "network_centrality": round(score_val * 0.3, 2),
                    "mo_escalation_score": round(score_val * 0.2, 2),
                    "associate_risk_avg": round(score_val * 0.1, 2),
                },
                human_reviewed=True,
            ))
        await session.flush()
        persons.extend(p.id for p in new_people)

    crime_head, crime_sub_head = await _get_or_create_financial_crime_head(session)
    units_by_district = await _get_or_create_units(session, districts)

    cases = (await session.execute(select(CaseMaster.id))).scalars().all()
    cases = list(cases)
    new_case_count_by_district_year: dict = {}

    # Per-district minimum, not a flat total: HawkesForecastService.forecast()
    # bails with "insufficient_data" below 10 incidents for a given
    # (district, crime_head) pair, so a pool that's large in aggregate but
    # thin per district still renders an empty Spatial Hotspots tab. Confirmed
    # live -- 28 cases spread over 8 districts gave every district 1-6 and no
    # district could fit an ETAS model.
    existing_fin_by_district = dict(
        (
            await session.execute(
                select(CaseMaster.district_id, func.count())
                .where(CaseMaster.crime_head_id == crime_head.id)
                .group_by(CaseMaster.district_id)
            )
        ).all()
    )

    new_cases = []
    new_case_district = []
    for district in districts:
        have = existing_fin_by_district.get(district.id, 0)
        needed = max(0, per_district_cases - have)

        # Generate as parent/offspring clusters, NOT uniform-random dates and
        # locations. This matters because the Hawkes/ETAS model on the Trends
        # page exists specifically to separate chronic background risk from
        # acute *near-repeat* risk -- a crime temporarily elevating risk
        # nearby, decaying over days. Sampling dates uniformly across a year
        # and coordinates uniformly across a district produces data with
        # literally zero near-repeat structure, so the model honestly reports
        # "100% chronic / 0% acute" and the hotspot map renders as one flat
        # uniform blob. Confirmed live before this change. Real offense data
        # clusters; so must synthetic data if the forecast tab is to show
        # anything meaningful.
        base_lat, base_lon = DEFAULT_DISTRICT_COORDS.get(district.name, (12.9716, 77.5946))
        schedule: list[tuple] = []

        # Values are "days ago" -- a LARGER number is further in the past.
        #
        # Two things force this layout. First, the ETAS kernel decays at
        # exp(-beta*days) with beta~=1.0 and is hard-cut at 30 days, so only
        # incidents from the last ~3 weeks affect a forecast targeted at
        # today. Second, HawkesETASService._compute_intensity uses a single
        # scalar `params.mu` as the background for EVERY grid cell, so the
        # background layer is spatially flat by construction -- all visible
        # variation in the hotspot map, and therefore the entire High/Medium/
        # Low spread in surveillance priorities (which tiers on
        # rate/max_rate), comes from near-repeat contributions alone.
        #
        # A single recent cluster therefore renders as a handful of hot cells
        # on an otherwise uniform field, which is what the flat-looking map
        # and the all-"High" priority list were both showing. Several
        # clusters at different places, staggered across the active window,
        # produce a genuinely graded surface instead.
        # Deliberately only a FEW recent clusters, not a share of the total.
        # _fit_etas sets the flat background to mu = n / span_days, so packing
        # every case into the last few weeks collapses the span, inflates mu,
        # and drowns the near-repeat layer it was supposed to expose --
        # measured live: filling all 24 cases from recent clusters pushed the
        # background from 0.1 to ~1.04 and cut hotspot contrast from 2.4x to
        # 1.16x. Most cases must stay spread over months to keep mu small.
        # Explicit hot / warm / cool recency rather than a random draw over
        # the window. exp(-beta*days) with beta~=1.0 means a cluster 20 days
        # old contributes ~2e-9 -- indistinguishable from nothing -- so a
        # uniform random pick over 2-26 days usually produced no visible
        # near-repeat at all (measured: 0 elevated cells). Three fixed bands
        # guarantee one strong, one moderate and one faint hotspot, which is
        # what gives the priority list an actual High/Medium/Low spread.
        recent_bands = [(1, 2), (4, 6), (9, 12)]
        for band_lo, band_hi in recent_bands:
            if len(schedule) >= needed:
                break
            parent_day = rng.randint(band_lo, band_hi)
            # Spread clusters across the district rather than stacking them.
            parent_lat = base_lat + rng.uniform(-0.10, 0.10)
            parent_lon = base_lon + rng.uniform(-0.10, 0.10)
            schedule.append((parent_day, parent_lat, parent_lon))

            # Offspring: triggered just after the parent (so 0-2 fewer days
            # ago) and within ~0.5km. Both bounds are tied to the kernel this
            # feeds: the spatial term is a Gaussian with sigma=0.5km, so
            # offspring scattered a few km out fall outside their own
            # parent's influence and stop reinforcing the hotspot; and a
            # loose day offset would drag a "cool" cluster into the hot band,
            # flattening the graded surface the tiers depend on.
            for _ in range(rng.randint(2, 3)):
                if len(schedule) >= needed:
                    break
                schedule.append((
                    max(0, parent_day - rng.randint(0, 2)),
                    parent_lat + rng.uniform(-0.004, 0.004),
                    parent_lon + rng.uniform(-0.004, 0.004),
                ))

        # Remainder spread over the older window -- invisible to the forecast
        # (>30 days) but needed so Temporal Seasonality has months of history
        # rather than a single recent spike.
        while len(schedule) < needed:
            schedule.append((
                rng.randint(35, _WINDOW_DAYS),
                base_lat + rng.uniform(-0.12, 0.12),
                base_lon + rng.uniform(-0.12, 0.12),
            ))

        for offset_day, lat, lon in schedule[:needed]:
            report_date = _TODAY - timedelta(days=max(0, offset_day))
            new_cases.append(
                CaseMaster(
                    crime_no=f"SYN/{district.code}/{uuid.uuid4().hex[:6].upper()}/{_TODAY.year}",
                    district_id=district.id,
                    unit_id=rng.choice(units_by_district[district.id]).id,
                    crime_head_id=crime_head.id,
                    crime_sub_head_id=crime_sub_head.id,
                    gravity_offence_id=crime_sub_head.gravity_offence_id,
                    date_reported=report_date,
                    incident_from_date=report_date,
                    incident_time=time(rng.randint(0, 23), rng.choice([0, 15, 30, 45])),
                    latitude=round(lat, 6),
                    longitude=round(lon, 6),
                    brief_facts="Synthetic financial-crime case generated for typology-driven detection testing.",
                )
            )
            new_case_district.append(district)
            key = (district.id, report_date.year)
            new_case_count_by_district_year[key] = new_case_count_by_district_year.get(key, 0) + 1

    if new_cases:
        log.info(f"Creating {len(new_cases)} financial cases so every district clears the Hawkes 10-incident minimum")
        session.add_all(new_cases)
        await session.flush()
        cases.extend(c.id for c in new_cases)
        await _link_accused(session, new_cases, persons, rng)

        # Background crime of OTHER types, so financial crime lands at a
        # believable share of the dataset instead of dominating it.
        # Without this, seeding enough financial cases to satisfy the Hawkes
        # per-district minimum left the database at 112 financial vs 2 theft
        # -- which made every cross-crime-type view read as "98% of crime in
        # Karnataka is financial." Most visibly, Sociological Insights'
        # victim demographics showed "100% Cyber Crime" for every age cohort,
        # arithmetically correct and completely misleading. Real NCRB
        # proportions put property/theft offences far above economic
        # offences, so the mix below is weighted that way.
        background = await _seed_background_crime(
            session, districts, units_by_district, persons, rng
        )
        if background:
            cases.extend(c.id for c in background)

        # CrimeStatAggregate rows -- what get_crime_stats()/get_correlation_matrix()
        # in socio_insights.py actually read, separate from the CaseMaster rows
        # themselves (that table is a pre-aggregated reporting layer, not
        # something derived live from case counts elsewhere in this codebase).
        for (district_id, year), count in new_case_count_by_district_year.items():
            existing = await session.execute(
                select(CrimeStatAggregate).filter_by(
                    district_id=district_id, year=year, crime_head_id=crime_head.id
                )
            )
            row = existing.scalar_one_or_none()
            if row is None:
                session.add(CrimeStatAggregate(
                    district_id=district_id, year=year, crime_head_id=crime_head.id,
                    count=count, chi_weighted_count=count * 4.0,  # matches the Heinous gravity chi_weight set above
                ))
            else:
                row.count += count
                row.chi_weighted_count = (row.chi_weighted_count or 0) + count * 4.0

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
            start = self._random_date(_TODAY - timedelta(days=_WINDOW_DAYS), _TODAY - timedelta(days=20))

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
            spike_date = self._random_date(_TODAY - timedelta(days=_WINDOW_DAYS), _TODAY - timedelta(days=15))

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
            start = self._random_date(_TODAY - timedelta(days=_WINDOW_DAYS), _TODAY - timedelta(days=30))

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
                self._random_date(_TODAY - timedelta(days=_WINDOW_DAYS), _TODAY),
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
            
            # Link Person to both accounts in transaction to show account nodes in graph explorer
            if row["linked_person_id"]:
                pid = str(row["linked_person_id"])
                await graph_db.execute_query(
                    """
                    MERGE (p:Person {id: $pid})
                    MERGE (a:Account {account_no: $from_acc})
                    MERGE (p)-[r:HAS_ACCOUNT]->(a)
                    SET r.updated_at = datetime()
                    """,
                    {"pid": pid, "from_acc": row["from_account"]},
                )
                await graph_db.execute_query(
                    """
                    MERGE (p:Person {id: $pid})
                    MERGE (a:Account {account_no: $to_acc})
                    MERGE (p)-[r:HAS_ACCOUNT]->(a)
                    SET r.updated_at = datetime()
                    """,
                    {"pid": pid, "to_acc": row["to_account"]},
                )

        # Seed synthetic PREDICTED_LINK relationships
        unique_pids = sorted(list({str(row["linked_person_id"]) for row in rows if row["linked_person_id"]}))
        print(f"Seeding synthetic PREDICTED_LINK relationships for {len(unique_pids)} suspects...")
        for i in range(0, len(unique_pids) - 1, 4):
            pid1 = unique_pids[i]
            pid2 = unique_pids[i + 1]
            await graph_db.execute_query(
                """
                MERGE (a:Person {id: $pid1})
                MERGE (b:Person {id: $pid2})
                MERGE (a)-[r:PREDICTED_LINK]-(b)
                SET r.confidence = $confidence,
                    r.model_version = 'GCN-LinkPredict-v2',
                    r.source_tool = 'Co-Offending & Structured Transfer Linker',
                    r.evidence = 'Shared IP logins and common structured cash recipients within 48h',
                    r.updated_at = datetime()
                """,
                {"pid1": pid1, "pid2": pid2, "confidence": round(0.52 + (i % 5) * 0.08, 2)},
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


async def _sync_accused_to_neo4j(session) -> None:
    """Mirrors PersonCaseRole ACCUSED rows into Neo4j as
    (Person)-[:ACCUSED_IN]->(Incident), carrying the case's unit_id.

    Both early-warning detectors traverse Neo4j, not Postgres:
    detect_communities() walks Person-ACCUSED_IN->Incident<-ACCUSED_IN-Person
    to find co-offending cells, and get_multi_jurisdiction_offenders() reads
    DISTINCT i.unit_id per person. Writing the PersonCaseRole rows to Postgres
    alone leaves both blind -- confirmed live: 218 accused rows in Postgres
    still produced zero ORGANIZED_GROUP/REPEAT_OFFENDER alerts until these
    edges existed.
    """
    rows = (
        await session.execute(
            select(
                PersonCaseRole.person_id,
                PersonCaseRole.case_id,
                CaseMaster.unit_id,
                CaseMaster.crime_no,
                Person.full_name,
            )
            .join(CaseMaster, CaseMaster.id == PersonCaseRole.case_id)
            .join(Person, Person.id == PersonCaseRole.person_id)
            .where(PersonCaseRole.role == PersonRole.ACCUSED)
        )
    ).all()

    await graph_db.connect()
    try:
        for person_id, case_id, unit_id, crime_no, full_name in rows:
            await graph_db.execute_query(
                """
                MERGE (p:Person {id: $pid})
                SET p.name = $name
                MERGE (i:Incident {id: $cid})
                SET i.unit_id = $unit_id, i.crime_no = $crime_no
                MERGE (p)-[r:ACCUSED_IN]->(i)
                SET r.updated_at = datetime()
                """,
                {
                    "pid": str(person_id), "cid": str(case_id),
                    "unit_id": unit_id, "crime_no": crime_no, "name": full_name,
                },
            )
        log.info(f"Synced {len(rows)} ACCUSED_IN edges to Neo4j (co-offending + jurisdiction graph)")
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

            await _sync_accused_to_neo4j(session)
    finally:
        await admin_engine.dispose()

    GROUND_TRUTH_PATH.write_text(json.dumps(gen.ground_truth, indent=2))
    log.info("Ground truth written", path=str(GROUND_TRUTH_PATH), count=len(gen.ground_truth))

    await _sync_to_neo4j(rows)
    log.info("Synced Person nodes + TRANSACTED_WITH edges to Neo4j")


if __name__ == "__main__":
    asyncio.run(seed())
