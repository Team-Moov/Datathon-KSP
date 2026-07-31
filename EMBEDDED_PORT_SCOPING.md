# Embedded Poly-Store Port — Concrete Scoping

**Goal:** replace Postgres+pgvector+Neo4j+Redis with an in-process embedded
poly-store — **SQLite (relational) + LanceDB (vector) + Kuzu (graph)** — so the
whole backend deploys as one self-contained AppSail container, no external DB
servers.

**Method:** grounded in an actual grep/read of the data layer, not estimates.
Backend data layer ≈ **1,826 LOC** across models + repositories + core infra.

---

## 1. Verdict up front

| | |
|---|---|
| **Total effort** | **~5–6 focused days** for someone who knows the codebase |
| **Biggest chunks** | Graph (Neo4j→Kuzu + Louvain→networkx) ~2d; Vector (pgvector→LanceDB) ~1d |
| **Biggest RISK** | dropping RLS — must verify app-layer district scoping exists on *every* table, not just cases |
| **Mechanical majority** | model type swaps (~35 sites) are find/replace |
| **What does NOT change** | all FastAPI endpoints' business logic, permissions matrix, audit logic, sentence-transformers embeddings, networkx centrality, Hawkes/risk math |

**Kuzu speaks Cypher**, so graph queries port with dialect edits rather than a
rewrite — the one exception is GDS (`CALL gds.louvain`), which has no Kuzu
equivalent and moves to networkx (you already do PageRank/betweenness in networkx).

---

## 2. Change surface by store

### 2a. Relational: Postgres → SQLite (`sqlite+aiosqlite`)

**Models (18 files, ~1,400 LOC) — mostly mechanical type swaps:**

| Postgres type | Count | → SQLite | Note |
|---|---|---|---|
| `UUID(as_uuid=True)` | 21 | SQLAlchemy 2.0 generic `Uuid` | dialect-agnostic; stores as CHAR(32) on SQLite |
| `JSONB` | 9 | generic `JSON` | one-line import swap |
| `ARRAY(String)` | 2 | `JSON` column + list handling | `Person.aliases`, `CriminalHistory.prior_incident_ids` — small logic change |
| `Vector(384)` | 1 | **remove from SQLite** | vectors live in LanceDB now (`models/vector.py`) |

→ **~35 edit sites, ~0.5 day, low risk** (compile-checked). `func.now()`,
`server_default`, relationships all port unchanged.

**`core/database.py` (205 LOC) — the significant rewrite:**
- `create_async_engine(asyncpg)` → `aiosqlite` engine (async supported ✅)
- **Delete** the entire RLS layer: `app_runtime` role creation, `CREATE POLICY`,
  `current_setting('app.current_role')` / `NULLIF(...)::integer` blocks (lines ~112–142)
- **Delete** the per-request `SET LOCAL` session-variable setting
- `init_db()` shrinks to: `create_all` + `schema_upgrades` (SQLite-compatible) +
  create Kuzu schema + create LanceDB tables
- → **205 → ~90 LOC, ~0.5 day**, but see RISK (§3)

**Repositories (5 files, 323 LOC) — mostly portable ORM:**
- `base.py` (71), `user_repository.py` (26), `person_repository.py` (58): generic
  ORM CRUD → **no change** beyond the model type swaps
- `case_repository.py` (103): **keep** `_apply_district_scope` (lines 35–37) — this
  is now the *only* district isolation, so it stays and gets audited (§3)
- `vector_repository.py` (65): **rewritten** — see 2b

**Raw SQL (`text()`) — 13 blocks** across `analytics_tasks.py`,
`risk_profiling._get_mo_escalation`, socio, ml_bridge:
- Most are ANSI-portable. Watch: `DISTINCT ON` (Postgres-only, in ml_bridge),
  `::` casts, `NULLS FIRST`. Each needs a dialect check.
- → **~0.5 day**

### 2b. Vector: pgvector → LanceDB (4 files, ~200 LOC)

| File | Change |
|---|---|
| `models/vector.py` (34) | drop the `Vector` column; `vector_chunk` metadata can stay in SQLite or move fully to LanceDB |
| `repositories/vector_repository.py` (65) | **rewrite** the cosine query (`embedding <=> :q`) → `lancedb_table.search(vec).limit(k)` |
| `services/embedding_service.py` (110) | keep sentence-transformers; write/read embeddings via LanceDB instead of pgvector |
| `services/ingestion_service.py`, `investigator_support.py` | update the few vector store/query call sites |

Embeddings still come from `all-MiniLM-L6-v2` (384-dim) — **only the storage/query
backend changes.** → **~1 day, contained.**

### 2c. Graph: Neo4j → Kuzu (4 files, ~500 LOC) — the tent-pole

| File | LOC | Change |
|---|---|---|
| `core/graph_db.py` | 136 | **rewrite** the driver wrapper: bolt session → embedded Kuzu connection; drop/relocate the Redis cache (→ Catalyst Cache or in-memory) |
| `services/graph_sync_service.py` | 231 | port ~10 Cypher upserts; Kuzu supports `MERGE`/`MATCH` but property syntax + `datetime()` differ |
| `services/analytics/network_analysis.py` | 135 | `detect_communities()` uses **`CALL gds.louvain`** → **reimplement in networkx** (`networkx.community.louvain_communities`); PageRank/betweenness already networkx ✅ |
| `services/analytics/financial_crime.py` | — | its graph-shape queries (cycles/fan-in-out) via `TRANSACTED_WITH` → Kuzu Cypher or networkx |

**15 Cypher queries total.** Kuzu-Cypher dialect notes: no GDS, no `datetime()`,
schema must be pre-declared (Kuzu is typed/columnar). → **~1.5–2 days.**

### 2d. Cache: Redis → Catalyst Cache or in-memory
- Only touchpoint is the query cache in `graph_db.py`. Swap to Catalyst Cache SDK,
  or an in-process LRU for demo. → **~0.25 day.**

---

## 3. The one real RISK: dropping RLS safely

RLS currently protects **every table** via the `app_runtime` role. The app-layer
filter is confirmed present for **cases** (`case_repository._apply_district_scope`).
**Before shipping, audit that district scoping is enforced in-query for every
other district-bound table** — persons, financial_transaction, documents,
person_case_role. Any endpoint that relied on RLS as its *only* filter becomes a
cross-district leak the moment RLS is gone.

- **Mitigation:** a single reusable `apply_district_scope(stmt, user)` applied in
  each repository, mirroring the cases one. ~0.5 day of audit + fills.
- This is a **security-correctness task**, so budget review time, not just code.

---

## 4. Supporting changes

| Item | Effort |
|---|---|
| `init_db()` + `seed_demo_data.py` — SQLite tables + Kuzu schema + LanceDB tables; graph sync + financial edge writes hit Kuzu | ~0.5 day |
| `analytics_tasks.py` (367) — swap async_engine→SQLite, Neo4j upsert→Kuzu, `DISTINCT ON` fix | folded into above |
| **Persistence** — bake seeded `*.db`/Kuzu-dir/LanceDB-dir into the image (demo), OR Stratus download-on-boot / upload-on-write | ~0.5 day |
| `requirements.txt` — drop `asyncpg`,`neo4j`,`pgvector`,`redis`; add `aiosqlite`,`kuzu`,`lancedb` | trivial |
| `config.py` — replace PG/Neo4j/Redis settings with file paths | ~0.25 day |
| Frontend | **untouched by this port** (separate blocker: missing `src/lib`) |

---

## 5. Effort roll-up

| Workstream | Effort | Risk |
|---|---|---|
| Model type swaps | 0.5 d | Low |
| `database.py` rewrite (drop RLS/roles) | 0.5 d | Med (see §3) |
| **RLS-removal audit** (every table scoped in-app) | 0.5 d | **High — security** |
| Vector → LanceDB | 1.0 d | Low |
| **Graph → Kuzu + Louvain→networkx** | 1.5–2.0 d | Med |
| Raw SQL dialect fixes | 0.5 d | Low |
| init_db + seed rewrite | 0.5 d | Low |
| Persistence (bake/Stratus) | 0.5 d | Low |
| Config/deps/local run | 0.25 d | Low |
| **Total** | **~5–6 focused days** | |

---

## 6. Hard constraints (unchanged from the earlier discussion)

1. **Single writer / single AppSail instance** — embedded stores are single-process;
   autoscale to 2+ instances → each gets its own file copy → split-brain. Pin to
   one instance or treat extras as read-only.
2. **Ephemeral disk** — durability comes from bake-in (demo) or Stratus snapshot,
   not the filesystem.
3. **You lose RLS (→ app layer) and GDS (→ networkx)** — both already have the
   app-layer/networkx machinery partly in place, which is why this is a port and
   not a rewrite.

---

## 7. Recommendation

- **Scale of job:** medium — ~5–6 days, and *most* of it is mechanical or already
  half-done (networkx centrality exists, app-layer case scoping exists, embeddings
  are already local). The genuinely new code is the Kuzu graph adapter and the
  LanceDB vector adapter.
- **Do it if** you're committing to Catalyst as the deployment target and want a
  single self-contained artifact with no external DB bills. It's the "correct"
  end-state for this platform on Catalyst.
- **Don't do it yet if** the priority is a *running demo this week* — external
  managed Postgres+Neo4j (Strategy B) gets you live with near-zero data-layer
  change, and this port can follow.
- **Regardless:** the frontend `src/lib` blocker and the never-run-live backend
  are higher priority than either deployment path — nothing ships until those are
  resolved.

Suggested order if proceeding: **(1)** models + `database.py` + RLS audit →
**(2)** LanceDB vector adapter → **(3)** Kuzu graph adapter + Louvain→networkx →
**(4)** init_db/seed + persistence → **(5)** local end-to-end run → **(6)** AppSail.
