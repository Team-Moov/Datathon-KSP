# Financial Crime module — branch `financial-crime-detection`

This closes the gap found in the existing backend: the schema, service stub,
and endpoints for financial crime detection already existed
(`app/models/financial.py`, `app/services/analytics/financial_crime.py`,
`app/api/v1/endpoints/financial.py`), but nothing populated the table, two of
the three detectors were looser than the real typologies, and community
detection (named in design doc §9.3 alongside cycle detection and
degree-ratio) had no implementation at all.

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

- `HIGH_VALUE` is a placeholder alert type for organized clusters until the
  `ORGANIZED_CLUSTER` enum member lands (see `enums_patch.md`).
- No test coverage beyond the ground-truth precision/recall check — no
  adversarial/stress-test variants yet (discussed separately: current
  numbers prove the pipeline is wired correctly, not that it generalizes).
