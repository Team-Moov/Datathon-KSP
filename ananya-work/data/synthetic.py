"""
Synthetic Crime Data Generator
================================
Generates a schema-consistent synthetic dataset for the crime-analytics
hackathon build: Persons, Incidents, Offenses, Case_Person_Role, MO-linkage
ground-truth series, district socio-economic/crime aggregates, and a small
financial-transaction set.

WHY THIS GENERATOR IS STRUCTURED THE WAY IT IS
------------------------------------------------
A naive random generator (random names, random dates, random crime types)
produces data that LOOKS realistic but has no learnable structure. Each of
the three "properly built" ML components needs something specific baked in:

  1. Risk score (survival model) needs real time-to-event structure, so a
     subset of persons is explicitly flagged as repeat offenders with
     multiple incidents spread across the calendar, some of which fall near
     the end of the window (-> genuine right-censoring, not just clean
     labels).

  2. MO linkage (Siamese/contrastive model) needs explicit ground-truth
     "same offender, same signature" series -- MO_LINKAGE_SERIES.csv is
     the actual training-label file: which incidents belong to the same
     offender, with narrative text deliberately paraphrased and a couple of
     structured fields perturbed per incident, so the model has to learn
     the underlying signature rather than exact-string-matching.

  3. Lead recommendation (node2vec) needs a graph with real temporal
     structure -- every co-offending edge is timestamped via its incident
     date, so a "graph as of 6 months ago" holdout split is meaningful.

WHAT'S REAL VS. PLACEHOLDER IN THIS FILE
------------------------------------------
- District list: REAL (Karnataka's 31 districts).
- National crime-rate priors (per 100k): REAL, from NCRB's 2023 published
  national rates, used to weight how often each crime head is generated.
  Source: NCRB "Crime in India" 2023 report, national rates.
- District-level socio-economic figures (literacy/unemployment/
  urbanization/sex ratio): PLACEHOLDER, randomized within realistic
  Karnataka-like ranges. Replace REAL_DISTRICT_STATS below with actual
  NDAP (Census 2011 + NFHS-4/5) downloads before using this for a real
  demo -- data.gov.in and NDAP are not reachable from this sandbox's
  network, so this could not be fetched automatically.
- CHI-style severity weights: PLACEHOLDER relative-harm scores (1-100)
  that preserve the correct rank ordering (murder > rape > dacoity >
  robbery > kidnapping > hurt > burglary > theft) but are NOT the
  validated Cambridge Institute of Criminology / NPA India CHI
  transposition table. Source that table if you can for the real demo.

Usage:
    python generate_synthetic_data.py --out-dir ./output
    python generate_synthetic_data.py --n-persons 800 --n-incidents 1500 \
        --n-mo-series 130 --months 24 --seed 42 --out-dir ./output
"""

import argparse
import csv
import os
import random
from datetime import date, timedelta

from faker import Faker

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

KARNATAKA_DISTRICTS = [
    "Bagalkot", "Ballari", "Belagavi", "Bengaluru Rural", "Bengaluru Urban",
    "Bidar", "Chamarajanagar", "Chikballapur", "Chikkamagaluru", "Chitradurga",
    "Dakshina Kannada", "Davanagere", "Dharwad", "Gadag", "Hassan", "Haveri",
    "Kalaburagi", "Kodagu", "Kolar", "Koppal", "Mandya", "Mysuru", "Raichur",
    "Ramanagara", "Shivamogga", "Tumakuru", "Udupi", "Uttara Kannada",
    "Vijayapura", "Vijayanagara", "Yadgir",
]

# Real NCRB 2023 national rates per 100,000 population. Used only as
# *relative weights* for how often each crime head appears -- not scaled to
# an actual population count, since this is a demo-scale synthetic dataset.
CRIME_RATE_PRIORS = {
    "Murder": 2.0,
    "Attempt to Murder": 3.0,
    "Rape": 4.4,
    "Kidnapping and Abduction": 8.2,
    "Dacoity": 0.5,
    "Robbery": 1.7,
    "Burglary": 7.7,
    "Theft": 49.5,
    "Riots": 2.8,
    "Criminal Breach of Trust": 3.0,
    "Cheating": 13.0,
    "Arson": 1.0,
    "Hurt / Grievous Hurt": 7.2,
    "Dowry Death": 0.9,
}

# PLACEHOLDER relative-harm weights (1-100 scale), rank-ordering only.
# Replace with the real Cambridge/NPA CHI transposition table if sourced.
CHI_SEVERITY_WEIGHTS = {
    "Murder": 100, "Dowry Death": 90, "Rape": 85, "Attempt to Murder": 70,
    "Dacoity": 60, "Kidnapping and Abduction": 55, "Arson": 40,
    "Robbery": 45, "Hurt / Grievous Hurt": 35, "Riots": 20,
    "Criminal Breach of Trust": 25, "Cheating": 20, "Burglary": 15,
    "Theft": 8,
}

# MO signature templates per crime head: (narrative_template, signature_tag)
# signature_tag is the "distinctive detail" a real offender repeats across
# a series -- this is what the Siamese model should learn to key on even
# when the surrounding narrative is paraphrased.
MO_TEMPLATES = {
    "Burglary": [
        ("Accused gained entry through the {entry} and removed {item} "
         "from the premises while occupants were {occupant_state}.",
         "entry:{entry}"),
    ],
    "Theft": [
        ("Accused was seen loitering near {location} before removing "
         "{item} and fleeing on a {vehicle}.",
         "vehicle:{vehicle}"),
    ],
    "Robbery": [
        ("Accused approached the victim near {location}, threatened them "
         "with a {weapon}, and fled with {item} on a {vehicle}.",
         "weapon:{weapon}"),
    ],
    "Cheating": [
        ("Accused posed as a {persona} and convinced the victim to transfer "
         "funds via {channel}, then became unreachable.",
         "channel:{channel}"),
    ],
    "Hurt / Grievous Hurt": [
        ("Accused engaged in an altercation with the victim near {location} "
         "over {dispute}, causing injury with a {weapon}.",
         "weapon:{weapon}"),
    ],
}

ENTRY_POINTS = ["rear window", "kitchen ventilator", "unlocked back door", "terrace access", "compound wall"]
ITEMS = ["jewellery", "cash and electronics", "a laptop", "two mobile phones", "a bag of valuables"]
OCCUPANT_STATES = ["away", "asleep", "at work"]
VEHICLES = ["two-wheeler", "auto-rickshaw", "bicycle", "on foot"]
WEAPONS = ["knife", "iron rod", "blunt object", "sharp weapon"]
LOCATIONS_GENERIC = ["a bus stop", "a market area", "a residential lane", "a parking lot", "a railway station"]
PERSONAS = ["bank official", "insurance agent", "government officer", "delivery agent"]
CHANNELS = ["UPI", "a fraudulent link", "a fake QR code", "phone banking"]
DISPUTES = ["a property boundary", "an old debt", "a family matter", "a road-rage incident"]

fake = Faker("en_IN")


# ---------------------------------------------------------------------------
# Districts + socio-economic layer
# ---------------------------------------------------------------------------

def generate_districts(rng):
    """PLACEHOLDER socio-economic figures -- swap in real NDAP data for the
    real demo. Composite index = simple percentile-rank average, matching
    the method used in the real district-index precedent (NDAP/Census2011/
    NFHS-4 study)."""
    rows = []
    for d in KARNATAKA_DISTRICTS:
        urban_bias = 1.0 if d in ("Bengaluru Urban", "Bengaluru Rural", "Dakshina Kannada", "Mysuru", "Dharwad") else 0.0
        literacy = round(rng.uniform(64, 78) + urban_bias * rng.uniform(6, 12), 1)
        unemployment = round(rng.uniform(3, 11) - urban_bias * rng.uniform(0, 2), 1)
        urbanization = round(rng.uniform(15, 40) + urban_bias * rng.uniform(35, 55), 1)
        sex_ratio = round(rng.uniform(955, 1020), 0)
        rows.append({
            "district_id": d.lower().replace(" ", "_"),
            "district_name": d,
            "year": 2024,
            "literacy_pct": literacy,
            "unemployment_pct": unemployment,
            "urbanization_pct": min(urbanization, 100.0),
            "sex_ratio": int(sex_ratio),
        })

    # composite index via percentile ranking across the four indicators
    # (literacy and urbanization: higher rank = higher value;
    #  unemployment: higher rank = LOWER value, i.e. inverted)
    def percentile_ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        for rank, idx in enumerate(order):
            ranks[idx] = rank / (len(values) - 1)
        return ranks

    lit = percentile_ranks([r["literacy_pct"] for r in rows])
    unemp_inv = percentile_ranks([-r["unemployment_pct"] for r in rows])
    urb = percentile_ranks([r["urbanization_pct"] for r in rows])
    for i, r in enumerate(rows):
        r["composite_stress_index"] = round((lit[i] + unemp_inv[i] + urb[i]) / 3, 3)

    return rows


# ---------------------------------------------------------------------------
# Persons
# ---------------------------------------------------------------------------

def generate_persons(rng, n_persons, districts, repeat_offender_frac=0.20):
    rows = []
    n_repeat = int(n_persons * repeat_offender_frac)
    repeat_flags = [True] * n_repeat + [False] * (n_persons - n_repeat)
    rng.shuffle(repeat_flags)

    for i in range(n_persons):
        d = rng.choice(districts)
        sex = rng.choice(["M", "M", "M", "F"])  # rough real-world skew in accused records
        name = fake.name_male() if sex == "M" else fake.name_female()
        rows.append({
            "person_id": f"P{i+1:05d}",
            "name": name,
            "age": rng.randint(18, 55),
            "sex": sex,
            "district_id": d["district_id"],
            "address_text": fake.address().replace("\n", ", "),
            "is_repeat_offender_pool": repeat_flags[i],
        })
    return rows


# ---------------------------------------------------------------------------
# MO-linkage ground-truth series + incidents/offenses/roles
# ---------------------------------------------------------------------------

def fill_template(template, rng):
    return template.format(
        entry=rng.choice(ENTRY_POINTS), item=rng.choice(ITEMS),
        occupant_state=rng.choice(OCCUPANT_STATES), vehicle=rng.choice(VEHICLES),
        weapon=rng.choice(WEAPONS), location=rng.choice(LOCATIONS_GENERIC),
        persona=rng.choice(PERSONAS), channel=rng.choice(CHANNELS),
        dispute=rng.choice(DISPUTES),
    )


def random_date(rng, start, months):
    end = start + timedelta(days=30 * months)
    delta_days = (end - start).days
    return start + timedelta(days=rng.randint(0, delta_days))


def generate_incidents(rng, persons, districts, n_incidents, n_mo_series, months, start_date):
    repeat_pool = [p for p in persons if p["is_repeat_offender_pool"]]
    non_repeat_pool = [p for p in persons if not p["is_repeat_offender_pool"]]
    rng.shuffle(repeat_pool)

    incidents, offenses, roles, mo_series_rows = [], [], [], []
    incident_counter = 1

    def new_incident(person_ids, crime_head, mo_text, mo_signature, occ_date, series_id=None):
        nonlocal incident_counter
        d = rng.choice(districts)
        incident_id = f"INC{incident_counter:06d}"
        incident_counter += 1
        incidents.append({
            "incident_id": incident_id,
            "fir_number": f"{d['district_id'][:3].upper()}/{occ_date.year}/{incident_counter:05d}",
            "district_id": d["district_id"],
            "date_occurred": occ_date.isoformat(),
            "date_reported": (occ_date + timedelta(days=rng.randint(0, 2))).isoformat(),
            "status": rng.choices(
                ["registered", "investigation", "chargesheet_filed", "closed"],
                weights=[0.15, 0.35, 0.35, 0.15],
            )[0],
        })
        offense_id = f"OFF{incident_counter:06d}"
        offenses.append({
            "offense_id": offense_id,
            "incident_id": incident_id,
            "crime_head": crime_head,
            "mo_text": mo_text,
            "mo_signature": mo_signature,
            "severity_weight": CHI_SEVERITY_WEIGHTS.get(crime_head, 10),
        })
        for pid in person_ids:
            roles.append({
                "incident_id": incident_id,
                "person_id": pid,
                "role": "accused",
            })
        if series_id:
            mo_series_rows.append({
                "series_id": series_id,
                "incident_id": incident_id,
                "offense_id": offense_id,
                "true_offender_person_id": person_ids[0],
            })
        return incident_id

    # --- 1. MO-linkage ground-truth series: repeat offenders with a
    # consistent signature across 2-5 paraphrased incidents ---
    crime_heads_with_mo = list(MO_TEMPLATES.keys())
    series_persons = repeat_pool[:n_mo_series]
    for i, person in enumerate(series_persons):
        series_id = f"SERIES{i+1:04d}"
        crime_head = rng.choice(crime_heads_with_mo)
        template, sig_template = rng.choice(MO_TEMPLATES[crime_head])
        # fix ONE signature element for the whole series (the "consistent"
        # part of the offender's behavior), vary everything else
        fixed_kwargs = dict(
            entry=rng.choice(ENTRY_POINTS), vehicle=rng.choice(VEHICLES),
            weapon=rng.choice(WEAPONS), channel=rng.choice(CHANNELS),
        )
        n_in_series = rng.randint(2, 5)
        for _ in range(n_in_series):
            varied = dict(fixed_kwargs)
            # vary the non-signature slots each time (paraphrase-like noise)
            varied["item"] = rng.choice(ITEMS)
            varied["occupant_state"] = rng.choice(OCCUPANT_STATES)
            varied["location"] = rng.choice(LOCATIONS_GENERIC)
            varied["persona"] = rng.choice(PERSONAS)
            varied["dispute"] = rng.choice(DISPUTES)
            mo_text = template.format(**varied)
            mo_signature = sig_template.format(**varied)
            occ_date = random_date(rng, start_date, months)
            new_incident([person["person_id"]], crime_head, mo_text, mo_signature, occ_date, series_id)

    # --- 2. Repeat offenders NOT in a clean series (noise: unrelated
    # repeat incidents by the same person -- real survival-analysis signal
    # without a clean MO story) ---
    leftover_repeat = repeat_pool[n_mo_series:]
    for person in leftover_repeat:
        n_events = rng.randint(1, 3)
        for _ in range(n_events):
            crime_head = rng.choices(
                list(CRIME_RATE_PRIORS.keys()),
                weights=list(CRIME_RATE_PRIORS.values()),
            )[0]
            template_list = MO_TEMPLATES.get(crime_head)
            mo_text = fill_template(template_list[0][0], rng) if template_list else f"Offense recorded under {crime_head}."
            occ_date = random_date(rng, start_date, months)
            new_incident([person["person_id"]], crime_head, mo_text, "none", occ_date)

    # --- 3. Crew-based incidents: persistent groups that co-offend
    # together repeatedly over time, with partial overlap per incident.
    # This is what gives the co-offending graph real community structure --
    # without it, "who gets grouped together" is pure noise and a temporal
    # link-prediction model (node2vec etc.) has nothing learnable to find.
    # A few "broker" persons deliberately span two crews, creating the
    # bridge structure betweenness centrality is meant to detect. ---
    crew_eligible = non_repeat_pool[:]
    rng.shuffle(crew_eligible)
    n_crews = max(1, len(crew_eligible) // 25)  # crews of ~5-7, roughly 1 crew per 25 eligible people
    crews = []
    idx = 0
    for _ in range(n_crews):
        size = rng.randint(4, 7)
        crew = crew_eligible[idx: idx + size]
        idx += size
        if len(crew) >= 3:
            crews.append(crew)
    # a handful of brokers: swap one member of crew i into crew i+1 too
    for i in range(0, len(crews) - 1, 4):
        if crews[i] and crews[i + 1]:
            broker = crews[i][0]
            if broker not in crews[i + 1]:
                crews[i + 1].append(broker)

    remaining_slots = max(n_incidents - len(incidents), 0)
    n_crew_slots = int(remaining_slots * 0.45)
    n_noise_slots = remaining_slots - n_crew_slots

    for _ in range(n_crew_slots):
        if not crews:
            break
        crew = rng.choice(crews)
        crime_head = rng.choices(
            list(CRIME_RATE_PRIORS.keys()), weights=list(CRIME_RATE_PRIORS.values()),
        )[0]
        template_list = MO_TEMPLATES.get(crime_head)
        mo_text = fill_template(template_list[0][0], rng) if template_list else f"Offense recorded under {crime_head}."
        occ_date = random_date(rng, start_date, months)
        subset_size = min(len(crew), rng.choice([2, 2, 3, 3, 4]))
        group = rng.sample(crew, subset_size)
        person_ids = [p["person_id"] for p in group]
        new_incident(person_ids, crime_head, mo_text, "none", occ_date)

    # --- 4. Remaining one-off incidents: unrelated persons, pure noise,
    # mostly solo with a small share of coincidental multi-accused groups
    # (real datasets have some of this too -- not every co-arrest implies
    # an ongoing crew). ---
    for _ in range(n_noise_slots):
        crime_head = rng.choices(
            list(CRIME_RATE_PRIORS.keys()),
            weights=list(CRIME_RATE_PRIORS.values()),
        )[0]
        template_list = MO_TEMPLATES.get(crime_head)
        mo_text = fill_template(template_list[0][0], rng) if template_list else f"Offense recorded under {crime_head}."
        occ_date = random_date(rng, start_date, months)

        if rng.random() < 0.08 and len(non_repeat_pool) >= 3:
            group = rng.sample(non_repeat_pool, rng.choice([2, 3]))
            person_ids = [p["person_id"] for p in group]
        else:
            person_ids = [rng.choice(non_repeat_pool)["person_id"]]

        new_incident(person_ids, crime_head, mo_text, "none", occ_date)

    return incidents, offenses, roles, mo_series_rows


# ---------------------------------------------------------------------------
# Financial transactions (minimal, typology-seeded)
# ---------------------------------------------------------------------------

def generate_financial_transactions(rng, persons, n_baseline=180, n_structuring_clusters=5, n_funnel=3):
    rows = []
    accounts = [f"ACC{p['person_id'][1:]}" for p in persons]
    person_by_account = {f"ACC{p['person_id'][1:]}": p["person_id"] for p in persons}
    tx_id = 1
    base_date = date(2024, 1, 1)

    def add_tx(frm, to, amount, d, pattern):
        nonlocal tx_id
        rows.append({
            "transaction_id": f"TXN{tx_id:05d}",
            "from_account": frm, "to_account": to,
            "amount": round(amount, 2), "date": d.isoformat(),
            "linked_person_id": person_by_account.get(frm, ""),
            "synthetic_pattern": pattern,
        })
        tx_id += 1

    for _ in range(n_baseline):
        frm, to = rng.sample(accounts, 2)
        add_tx(frm, to, rng.uniform(500, 200000), random_date(rng, base_date, 24), "none")

    # structuring: 3-4 deposits just under the 10 lakh CTR threshold
    for _ in range(n_structuring_clusters):
        frm, to = rng.sample(accounts, 2)
        cluster_start = random_date(rng, base_date, 20)
        for k in range(rng.randint(3, 4)):
            amt = rng.uniform(920000, 985000)
            add_tx(frm, to, amt, cluster_start + timedelta(days=k), "structuring")

    # funnel: dormant account gets a sudden large credit, then rapid withdrawal
    for _ in range(n_funnel):
        dormant = rng.choice(accounts)
        sources = rng.sample([a for a in accounts if a != dormant], 3)
        credit_date = random_date(rng, base_date, 20)
        for src in sources:
            add_tx(src, dormant, rng.uniform(150000, 400000), credit_date, "funnel_in")
        add_tx(dormant, rng.choice(accounts), rng.uniform(400000, 900000),
               credit_date + timedelta(days=1), "funnel_out")

    return rows


# ---------------------------------------------------------------------------
# Aggregation + I/O
# ---------------------------------------------------------------------------

def aggregate_crime_stats(incidents, offenses):
    by_incident = {i["incident_id"]: i for i in incidents}
    counts = {}
    for o in offenses:
        inc = by_incident[o["incident_id"]]
        year = inc["date_occurred"][:4]
        key = (inc["district_id"], year, o["crime_head"])
        counts[key] = counts.get(key, 0) + 1
    return [
        {"district_id": k[0], "year": k[1], "crime_head": k[2], "count": v}
        for k, v in counts.items()
    ]


def write_csv(path, rows):
    if not rows:
        return
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-persons", type=int, default=800)
    ap.add_argument("--n-incidents", type=int, default=1500)
    ap.add_argument("--n-mo-series", type=int, default=130)
    ap.add_argument("--months", type=int, default=24)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out-dir", type=str, default="./output")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    Faker.seed(args.seed)
    os.makedirs(args.out_dir, exist_ok=True)

    districts = generate_districts(rng)
    persons = generate_persons(rng, args.n_persons, districts)
    incidents, offenses, roles, mo_series = generate_incidents(
        rng, persons, districts, args.n_incidents, args.n_mo_series,
        args.months, date(2024, 1, 1),
    )
    transactions = generate_financial_transactions(rng, persons)
    crime_stats = aggregate_crime_stats(incidents, offenses)

    # strip helper-only field before writing Person.csv
    persons_out = [{k: v for k, v in p.items() if k != "is_repeat_offender_pool"} for p in persons]

    write_csv(os.path.join(args.out_dir, "district_socioeconomic.csv"), districts)
    write_csv(os.path.join(args.out_dir, "persons.csv"), persons_out)
    write_csv(os.path.join(args.out_dir, "incidents.csv"), incidents)
    write_csv(os.path.join(args.out_dir, "offenses.csv"), offenses)
    write_csv(os.path.join(args.out_dir, "case_person_role.csv"), roles)
    write_csv(os.path.join(args.out_dir, "mo_linkage_series.csv"), mo_series)
    write_csv(os.path.join(args.out_dir, "financial_transactions.csv"), transactions)
    write_csv(os.path.join(args.out_dir, "crime_stat_aggregate.csv"), crime_stats)

    print("Generated:")
    print(f"  districts:              {len(districts)}")
    print(f"  persons:                {len(persons)}  (repeat-offender pool: {sum(p['is_repeat_offender_pool'] for p in persons)})")
    print(f"  incidents:              {len(incidents)}")
    print(f"  offenses:               {len(offenses)}")
    print(f"  case_person_role rows:  {len(roles)}")
    print(f"  MO-linkage series rows: {len(mo_series)}  (series: {len(set(r['series_id'] for r in mo_series))})")
    print(f"  financial transactions: {len(transactions)}")
    print(f"  crime_stat_aggregate:   {len(crime_stats)}")
    print(f"\nWritten to: {os.path.abspath(args.out_dir)}")


if __name__ == "__main__":
    main()
