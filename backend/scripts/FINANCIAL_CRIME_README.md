# Financial Crime module — branch `financial-crime-detection`

This closes the gap found in the existing backend: the schema, service stub,
and endpoints for financial crime detection already existed
(`app/models/financial.py`, `app/services/analytics/financial_crime.py`,
`app/api/v1/endpoints/financial.py`), but nothing populated the table, two of
the three detectors were looser than the real typologies, and community
detection (named in design doc §9.3 alongside cycle detection and
degree-ratio) had no implementation at all.

## Detection features — what this actually catches, mechanically

Three real money-laundering typologies (India-grounded, not invented),
deliberately detected with rules + graph algorithms rather than ML — every
flag has to trace back to specific transactions as evidence, not a
black-box score (matches the platform's deterministic-agentic commitment,
design doc §1.3/§11).

### 1. Structuring / smurfing — `detect_structuring()`

Splitting a large sum into deposits that individually stay under India's
real ₹10 lakh Cash Transaction Report threshold (`CTR_THRESHOLD_INR`).

- For every `(from_account, to_account)` pair that transacted, walk their
  transactions in time order.
- Slide a **7-day window** (`STRUCTURING_WINDOW_DAYS`) across them.
- At each point: do the transactions currently in the window sum to
  **≥ ₹10L**, while every individual transaction in that window stays
  **< ₹10L**, with **at least 3 legs**? If yes, flag it.
- Confidence: `min(0.99, 0.6 + 0.05 * leg_count)` — more legs in the
  cluster, higher confidence.
- Evidence returned: the exact transaction IDs in the flagged window, the
  total amount, leg count.

### 2. Funnel / mule accounts — `detect_funnel_account()`

A dormant account suddenly receiving money from many sources, then
emptying out almost immediately.

- For a candidate account, find any burst of **≥ 5 distinct sources**
  (`FUNNEL_MIN_SOURCES`) sending money in within a **2-day window**
  (`FUNNEL_BURST_WINDOW_DAYS`).
- **Dormancy check (the fix made on this branch):** before flagging,
  require **zero transactions** on that account in the **60 days**
  (`FUNNEL_DORMANCY_DAYS`) immediately before the burst. A normally-busy
  account with lots of incoming payments does *not* count — this is what
  makes "dormant" in the typology name actually mean something.
- Then check: did **≥ 80%** (`FUNNEL_RATIO_MIN`) of the inflow leave again
  within a **5-day withdrawal window** (`FUNNEL_WITHDRAWAL_WINDOW_DAYS`)?
  If yes, flag it.
- Confidence: `min(0.99, 0.5 + 0.03 * source_count)`.
- Evidence returned: every inflow + outflow transaction ID in the burst.

### 3. Layering — `detect_cycles_in_graph()`

Money moved through a chain of intermediary accounts to obscure origin,
often looping back toward its source.

- Runs against the **account-level** `TRANSACTED_WITH` graph in Neo4j (see
  the architecture note below for why account-level, not person-level).
- Cypher cycle query: find any path of **2 to 6 hops** that starts and ends
  at the same `Account` node, with path length **≥ 3**.
- Confidence: fixed at `0.70` per cycle found (not currently scaled by
  cycle length — flagged as a possible improvement).
- Evidence returned: the account chain itself (`cycle_members`) and its
  length.

### 4. Organized clusters — `detect_organized_clusters()` (new on this branch)

Groups individually-flagged accounts into probable rings, rather than
reporting isolated hits — the third graph technique the design doc names
(§9.3: "cycle detection, in/out-degree ratio, community detection") that
had zero implementation before this branch.

- Takes every account flagged by the three detectors above.
- Pulls the subgraph of `TRANSACTED_WITH` edges connecting *only* those
  already-flagged accounts.
- Runs **Louvain community detection** (via `networkx`, not Neo4j GDS —
  deliberately avoids depending on the GDS plugin being present in
  whichever Neo4j image gets deployed) over that subgraph.
- Any community with **≥ 2 accounts** is reported as a cluster.
- Confidence: `min(0.95, 0.4 + 0.05 * cluster_size)`.

### Output shape — every detector returns this, no exceptions

Shaped like a real Suspicious Transaction Report, not an invented alert
format (design doc §9.5):

```json
{
  "typology": "structuring | funnel_account | layering | organized_cluster",
  "accounts_involved": ["ACC-xxxx", "..."],
  "evidence_trail": { "...typology-specific fields, always includes transaction_ids where applicable..." },
  "confidence": 0.0,
  "recommended_action": "Review and file STR with FIU-IND if confirmed",
  "disclaimer": "This is a system-generated lead based on transaction patterns. Analyst review and sign-off required before any action."
}
```

Confirmed to match the frontend's `SuspiciousTransactionAlert` TypeScript
interface (`frontend/src/features/financial/financialApi.ts`) field-for-field
— checked by reading the actual `.tsx` source, not assumed.

### Validated accuracy (against the generator's own ground truth — see the honesty note below)

| Typology | Precision | Recall |
|---|---|---|
| Structuring | 1.0 | 0.517 (known weak spot — window-reset logic misses some legs after the first flag) |
| Funnel | 1.0 | 1.0 |
| Layering | 1.0 | 0.941 |

**Read this honestly:** this proves the detectors are wired correctly
against the exact patterns they were designed to catch — it does **not**
prove they'd generalize to real laundering patterns that don't match these
exact shapes (structuring with irregular leg sizes, longer funnel
withdrawal windows, branching layering chains, etc.). No adversarial/stress
test exists yet — see "Not yet done" below.

## What's already applied on this branch

| File | Change |
|---|---|
| `scripts/seed_financial_transactions.py` | NEW |
| `app/services/analytics/financial_crime.py` | REPLACED (tightened structuring, dormancy-aware funnel, new organized-cluster detection) |
| `app/api/v1/endpoints/financial.py` | Two new routes appended: `/organized-clusters`, `/scan` |
| `scripts/validate_financial_crime.py` | NEW |
| `app/models/enums.py` | `FinancialAlertType.ORGANIZED_CLUSTER` added |

**Still needed once Postgres is actually running (nobody has run
`docker-compose up` yet, as of this branch):**
```bash
cd backend
docker-compose up -d postgres neo4j redis
alembic revision --autogenerate -m "add organized_cluster financial alert type"
alembic upgrade head
python -m scripts.seed_financial_transactions
python -m scripts.validate_financial_crime
```

## Rebased onto Vishy's branch (frontend + RLS/permissions rewrite)

This branch was rebased on top of `Vishy` after they pushed the frontend and
replaced `Role`/`require_roles` with the `Permission`/`require_permission`
capability system. Two things fixed as part of that:

- The two new endpoints (`/organized-clusters`, `/scan`) now use
  `require_permission(Permission.VIEW_FINANCIAL_RAW)`, matching what Vishy
  already applied to the original three routes -- the old `Role.ANALYST`/
  `Role.ADMIN` references no longer exist on this branch.
- `seed_financial_transactions.py` now connects via the **admin** engine
  (`settings.DATABASE_URL_ADMIN`), not `AsyncSessionFactory`. `case_master`
  has Row-Level Security keyed on `app.current_district_id`/`app.current_role`
  (see `core/database.py::_setup_runtime_role_and_rls`); a seeding script has
  no logged-in user to derive those session variables from, so the restricted
  `app_runtime` role would silently see **zero** `CaseMaster` rows instead of
  erroring -- `_get_or_create_pool()` would wrongly conclude none exist and
  invent its own every run. `seed_demo_data.py`'s own docstring documents
  hitting exactly this failure first; this fix follows the same pattern.
  `validate_financial_crime.py` does NOT need this -- it only reads
  `FinancialTransaction`, which has no RLS policy applied.
- Checked: `Permission.VIEW_FINANCIAL_RAW` is only granted to
  DSP/SP/DGP/CRIME_ANALYST tiers, which is exactly the district-unrestricted
  role set in the RLS policy -- so fallback-created `CaseMaster` rows having
  a NULL `district_id` never actually hides financial data from anyone
  authorized to view it in the first place. No fix needed there.
- Files moved from `app/scripts/` to `scripts/` to match the location
  `seed_demo_data.py` actually established (run as `python -m scripts.x`
  from `backend/`, not `python -m app.scripts.x`).

## What changed vs. what already existed

- **`detect_structuring`** — was a flat 30-day window summed across every
  counterparty touching an account. Now a proper rolling 7-day window
  per `(from_account, to_account)` pair, matching the real typology
  (structuring is about *legs between a specific source and destination*,
  not all activity on an account).
- **`detect_funnel_account`** — was missing the dormancy check, which is the
  literal defining word in the typology ("a *previously dormant* account
  suddenly receives..."). Added: no prior activity in the 60 days before
  the inflow burst, or it doesn't count.
- **`detect_cycles_in_graph`** — logic was already right, but queried
  `Person` nodes for cycles. Fixed to query `Account` nodes (see the
  architecture note below on why).
- **`detect_organized_clusters`** — entirely new. Louvain community
  detection (via networkx, not Neo4j GDS, to avoid a hard dependency on the
  GDS plugin being present) over the account-level graph, restricted to
  already-flagged accounts — groups individual hits into probable rings.

## One real architecture gap surfaced while building this — flag it to whoever owns `graph_sync_service.py`

`GraphSyncService.upsert_financial_edge()` is written to create a
`Person -[:TRANSACTED_WITH]-> Person` edge from two person IDs. But
`FinancialTransaction` only ever carries **one** `linked_person_id` per row —
there's no `Account -> Person` ownership table, so there's no way to know
*both* counterparties of a transaction as people, only one.

`seed_financial_transactions.py` works around this honestly, on two layers:
1. **Account-level graph** (`Account -[:TRANSACTED_WITH]-> Account`) — this is
   what the typologies are actually shapes in (fan-out/fan-in/cycles are
   account-graph properties). All detection in `financial_crime_service.py`
   runs against this layer.
2. **Person-level `FINANCIALLY_ASSOCIATED_WITH`** edges — inferred when two
   different people's transactions touch the same account. Deliberately
   *not* named `TRANSACTED_WITH`, so this weaker, inferred evidence never
   gets silently merged with a genuinely confirmed two-sided link (same
   principle the design doc already applies to predicted vs. confirmed
   network edges in §4).

If real account-ownership data ever exists, this can be upgraded to true
confirmed `TRANSACTED_WITH` person edges — until then, this is the honest
version of what the data actually supports.

## How to run it

```bash
cd backend
# containers up (postgres, neo4j, redis) per docker-compose.yml
python -m scripts.seed_financial_transactions
python -m scripts.validate_financial_crime
```

Ground truth (`financial_ground_truth.json`) is written next to the seed
script — it's for `validate_financial_crime.py` only, never inserted into
Postgres, and never shipped as part of the handoff schema.

## Not yet done / next if there's time

- No test coverage beyond the ground-truth precision/recall check — no
  adversarial/stress-test variants yet (see the honesty note above: current
  numbers prove the pipeline is wired correctly, not that it generalizes).
- `detect_cycles_in_graph`'s confidence is a fixed `0.70`, not scaled by
  cycle length like the other three detectors are — minor inconsistency,
  cheap to fix later.
- Structuring recall (0.517) could likely be improved by not resetting the
  sliding window entirely on first flag — currently misses legs that occur
  after an initial match within the same cluster.
