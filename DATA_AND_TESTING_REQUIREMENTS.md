# Data & Testing Requirements — Karnataka Crime Analytics Platform

**Purpose:** everything required to *power up, seed, test, and demo* the entire
project — the services, the environment variables, and (the bulk of this doc)
**every category of data each feature needs, in what format, at what volume, and
what breaks if it's missing.**

This is a build-status-aware document. Where a feature cannot currently run
(frontend, GWR, live integration), that is stated instead of pretended around.

---

## 0. TL;DR — the two honest ways to run this

There are **two independent data-loading paths**, and they do **not** currently
converge on the same person identities:

| Path | Populates | Powers | Status |
|---|---|---|---|
| **A. Backend demo seeder** (`scripts.seed_demo_data`) | Backend Postgres + Neo4j | API, workspace, network, financial, chat | ✅ works (never run live, but self-contained) |
| **B. Ananya ML pipeline + `ml_bridge`** | Ananya's own Postgres → ETL → backend | ML link-prediction, graph metrics, survival risk | 🟡 ML pipeline ✅ green; bridge untested |

**Critical caveat:** Path A creates persons with random `uuid4` and **no
`source_person_id`**. Path B creates persons with `id = uuid5(namespace,
ananya_id)` and sets `source_person_id`. **The ML insights from Path B only
attach to persons loaded by Path B.** If you demo on seeded data (Path A), the
ML bridge writes nothing that matches. **Pick one path per person population**,
or reconcile them (see §9).

---

## 1. Infrastructure required to "power up everything"

| Service | Why | Required for |
|---|---|---|
| **PostgreSQL 15+ with `pgvector` + `pg_trgm`** | Relational core + vector search | Everything |
| **Neo4j 5.x with GDS plugin** | Graph store (co-offending, financial, communities) | Network analysis, Louvain, predicted links |
| **Redis** | Celery broker + query cache | Background analytics jobs |
| **Celery worker** | Async Hawkes fit, risk rescoring, link prediction | Trend/risk recompute tasks |
| **FastAPI backend** (`backend/`) | API surface | All endpoints |
| **Full ML stack** — `torch`, `transformers`, `sentence-transformers` (`all-MiniLM-L6-v2`) | Local embeddings; imported at startup | `/chat`, similar-case RAG, ingestion embed |
| **Groq API key** | LLM planning/narration + Whisper transcription | `/chat`, `/chat/voice`, `/cases/{id}/brief` |
| **Frontend build** (`frontend/`) | UI | ⚠️ **currently broken** — missing `src/lib` (see §10) |
| **(Path B only) 2nd Postgres** for Ananya + trained artifacts | ML training/inference source | `ml_bridge` ETL |

### Required environment variables (no insecure fallbacks — app refuses to start without them)
```
SECRET_KEY               # >= 32 chars
POSTGRES_PASSWORD        # owner/admin role
POSTGRES_APP_PASSWORD    # restricted app_runtime role (RLS applies to this role)
NEO4J_PASSWORD
GROQ_API_KEY             # real key required for chat/brief/voice; every other endpoint works without
ENVIRONMENT              # development | production  (MFA mock refused in production)
# Optional seed overrides:
SEED_DEMO_PASSWORD (default Demo@12345), SEED_ADMIN_EMAIL (admin@ksp.demo), SEED_ADMIN_PASSWORD
# Optional Path-B artifact locations:
LEAD_REC_ARTIFACTS_DIR (default /artifacts/lead_rec)
```

---

## 2. Data model overview — what has to exist and in what order

Load order is **FK-safe top to bottom**. Reference/lookup tables first, then
entities, then roles/links, then derived data.

```
TIER 1  Reference/lookup   state → district → unit_type → unit → court
                            crime_head → crime_sub_head → gravity_offence
                            act → section → act_section_association(link)
                            case_status_master
                            religion_master, caste_master, occupation_master
TIER 2  Users              user  (one per rank + admin)
TIER 3  Entities           person  (resolved cross-case identity)
TIER 4  Cases              case_master → case_stage_event, chargesheet_details
TIER 5  Roles/links        person_case_role, criminal_history
TIER 6  Narrative          document → vector_chunk (embeddings)
TIER 7  Financial          financial_transaction
TIER 8  Aggregates         socio_economic_indicator, crime_stat_aggregate
TIER 9  Derived (versioned) risk_score, mo_linkage_cluster, predicted_link,
                            person_graph_metric, district_composite_index
TIER 10 Graph (Neo4j)      Person/Incident/FinancialAccount nodes;
                            ACCUSED_IN, ASSOCIATED_WITH, TRANSACTED_WITH,
                            predicted_link edges
```

---

## 3. Reference / lookup data (TIER 1) — *nothing works without this*

Small, hand-curated. The demo seeder creates a minimal set; a full demo wants
real Karnataka reference data.

| Table | Key fields | Minimum for demo | Real-data source |
|---|---|---|---|
| `state` | name, code | Karnataka / KA | — |
| `district` | name, code, state_id | 2 (Bengaluru, Mysuru) | **31 real KA districts** |
| `unit_type` | name, hierarchy_level | Station=3, Circle=2 | KSP unit hierarchy |
| `unit` | name, unit_type_id, district_id, parent_unit_id | 2–3 stations | KSP station list |
| `court` | name | optional | e-Courts |
| `crime_head` | name, code | Theft | NCRB crime heads |
| `crime_sub_head` | crime_head_id, name, gravity_offence_id | Theft of motor vehicle | NCRB sub-heads |
| `gravity_offence` | label (Heinous/Non-Heinous), **chi_weight** | Non-Heinous=2.5 | **Cambridge/NPA CHI mapping** |
| `act` | name, short_name | IPC | — |
| `section` | act_id, section_number, description | 379 (Theft) | — |
| `act_section_association` | case_id, act_id, section_id | per case | — |
| `case_status_master` | status_name | "Under Investigation" | KSP `CaseStatusMaster` |
| `religion_master`, `caste_master`, `occupation_master` | id, name | optional (sensitive — masked) | KSP masters |

> **CHI weights matter:** `gravity_offence.chi_weight` is the severity anchor for
> risk scoring (§7 of design). Wrong/missing weights → meaningless risk scores.

---

## 4. Users (TIER 2) — RBAC / governance testing

Need **one user per role** to exercise permission matrix + district-scoped RLS.

`Role` enum: `CONSTABLE, INSPECTOR, DSP, SP, DGP, CRIME_ANALYST, POLICY_MAKER`

| Field | Format | Notes |
|---|---|---|
| email | string | login id |
| hashed_password | bcrypt | via `hash_password()` |
| full_name | string | |
| role | Role enum | |
| badge_number | string | e.g. `PC-4471` |
| district_id | int / null | **set only for CONSTABLE & INSPECTOR** (district-scoped) — this is what RLS isolation is tested against |
| unit_id | int / null | for scoped roles |

Seeder creates 7 rank personas + 1 admin (`admin@ksp.demo`). To test RLS
isolation you **need at least 2 districts and a scoped user in one** — a
Bengaluru constable must be provably unable to see the Mysuru case.

---

## 5. Persons (TIER 3) — the identity backbone

One row per **resolved real-world individual** (not per FIR appearance).

| Field | Format / enum | Needed by |
|---|---|---|
| id | UUID (backend) / TEXT (Ananya) | everything |
| full_name | string, indexed | search, graph labels |
| aliases | string[] | entity resolution, alias edges |
| date_of_birth / age_at_registration | date / int | victim-demographic aggregates |
| sex | `M/F/O/U` | aggregates |
| permanent_address / present_address | text | shared-address links (design; partial) |
| occupation_id | FK | profiling |
| **source_person_id** | string | **Path-B bridge key (uuid5 source id)** |
| human_verified | bool | governance gate |
| version | int | optimistic concurrency |

**Volume guidance for meaningful analytics:**
- Network/community detection: **≥ 300–800 persons**, with a **repeat-offender
  pool (~20%)** appearing in multiple cases — isolated persons produce isolated
  dots and empty communities.
- Ananya's generator makes **800 persons (160 repeat-offender pool)** — a good target.

---

## 6. Cases & roles (TIER 4–5) — core investigative data

### `case_master`
| Field | Format | Notes |
|---|---|---|
| crime_no | string, e.g. `THEFT-BLR-INDR-2025-0142` | encodes category+district+station+year |
| unit_id, district_id | FK | jurisdiction |
| incident_from_date, date_reported | date | **use dates relative to `today`** — financial & forecast windows look back 30–90 days |
| latitude, longitude | float | hotspot forecasting, map widgets |
| crime_head_id, crime_sub_head_id, gravity_offence_id | FK | classification + severity |
| case_status_id | FK | current status |
| brief_facts | text | **embedded into vector store** for RAG/similar-case |
| source_type | `FIR/CHARGESHEET/JUDGMENT/HISTORY_SHEET/STATEMENT/NEWS/FINANCIAL/GD` | |

### `case_stage_event` (status history — design §8.3)
`stage ∈ registered/investigation/chargesheet_filed/disposed/closed`, event_date, confidence.
Needed for **timeline widget** and honest procedural-status display.

### `chargesheet_details` (disposition — design §8.2)
`cstype ∈ Chargesheet / False Case / Undetected`, csdate. The real disposition signal.

### `person_case_role` — the co-offending source
| Field | Format |
|---|---|
| person_id, case_id | FK |
| role | `accused/victim/witness/complainant` |
| arrested, arrest_date, bail_granted | bool/date/bool |

> **This table is the single most important one for network analysis.** A
> co-offending edge = two persons with `role=ACCUSED` on the same `case_id`.
> No multi-accused cases → empty network.

### `criminal_history`
person_id, prior_incident_ids[], mo_pattern_summary, human_verified.

---

## 7. Narrative + vector data (TIER 6) — RAG / similar-case / chat

| Table | Field | Format | Powers |
|---|---|---|---|
| `document` | source_type, file_format, original_filename, raw_file_ref, extraction_method, confidence_score, linked_incident_id, human_verified | provenance backbone | Explainability, timeline |
| `vector_chunk` | embedding **vector(384)** (all-MiniLM-L6-v2), document_id, incident_id, chunk_type (`mo/gist/statement/chargesheet/news`) | 384-dim float | Similar-case RAG, semantic search |

**To test similar-case retrieval you need real narrative text** in
`brief_facts` / documents, embedded into `vector_chunk`. Thin/empty text → no
meaningful retrieval. Design principle: synthesize narrative text freely to fill
volume, but **never fake outcome distributions** (conviction rates etc.).

`DocumentFormat`: `pdf, docx, csv, xlsx, html, jpg, png, wav, mp3, geojson, shapefile, unknown`
`ExtractionMethod`: `direct_load, template_extraction, ner_relation, full_text_embed, transcription, gis_load, manual`

---

## 8. Financial transactions (TIER 7) — financial-crime detection

`financial_transaction`:

| Field | Format | Notes |
|---|---|---|
| from_account / to_account | string, e.g. `ACCT-9931-2200-4821` | graph endpoints |
| amount | numeric (INR) | thresholds |
| transaction_date | date | rolling 7/30-day windows |
| transaction_type | string (UPI, NEFT…) | |
| linked_person_id, linked_incident_id | FK | ties money to persons/cases |
| alert_type | `structuring/funnel_account/layering/high_value/organized_cluster` | |
| alert_confidence | float | |
| alert_details | JSONB | typology metadata |

**Typology-driven generation required (design §9 — like AMLNet), not random noise:**

| Typology | Graph shape | Data recipe |
|---|---|---|
| **Structuring/smurfing** | fan-out under threshold | **≥3–4 transfers to one account, each < ₹10,00,000 (1,000,000)**, summing over it, within the window. *A single transaction can never trigger it.* |
| **Funnel/mule** | fan-in → fan-out | dormant account, many inbound sources, then rapid emptying |
| **Layering** | cycle / long chain | money through intermediary accounts looping toward source |

> **Dates must be recent** (within 30–90 days of `today`) or detection returns nothing.

---

## 9. Aggregate socio-economic data (TIER 8) — sociological insights

**Architectural firewall:** these tables must **never** join to `person`.

`socio_economic_indicator` / Ananya `district_socioeconomic.csv`:
```
district_id, year, literacy_pct, unemployment_pct, urbanization_pct, sex_ratio, composite_stress_index
```
`crime_stat_aggregate`:
```
district_id, year, crime_head, count
```

- Grain: **district × year**. For correlation/trends want **multiple years × 31 districts**.
- Source: Census, NFHS, NCRB district-wise (real, public). Placeholder
  Karnataka-range figures acceptable for demo; label them as placeholder.
- `district_composite_index` (versioned): composite_score, composite_stress_index,
  **`gwr_coefficients` (JSONB)** — ⚠️ **the GWR coefficients are NOT computed by
  any code** (design §6 feature was cut; see §11). Table/endpoint exist but
  nothing populates real coefficients.

---

## 10. Derived / ML output data (TIER 9) — versioned, append-only

These are **produced by tools**, not hand-fed — but for a demo you can seed
representative rows.

| Table | Key fields | Produced by |
|---|---|---|
| `risk_score` | score, chi_weighted_harm, network_centrality, mo_escalation_score, associate_risk_avg, **shap_decomposition (JSONB)**, model_version, human_reviewed | `RiskProfilingService` / Ananya survival model |
| `mo_linkage_cluster` | offense_id, cluster_id, similarity_score, model_version | Jaccard (backend) / Siamese (Ananya) |
| `predicted_link` | person_id_a, person_id_b, confidence, source_tool, evidence, model_version | node2vec+logreg (Ananya) → bridge |
| `person_graph_metric` | person_id, pagerank, betweenness, community_id, graph_version | networkx / GDS |
| `district_composite_index` | composite_score, gwr_coefficients | composite_index.py |

All carry **model_version + timestamp and are never overwritten** (explainability
requirement).

---

## 11. Ananya CSV formats (Path B input) — exact headers

Generated by `ananya-work/data/synthetic.py --out-dir ./output` (verified runs green):

```
persons.csv                person_id, name, age, sex, district_id, address_text
incidents.csv              incident_id, fir_number, district_id, date_occurred, date_reported, status
offenses.csv               offense_id, incident_id, crime_head, mo_text, mo_signature, severity_weight
case_person_role.csv       incident_id, person_id, role
mo_linkage_series.csv      series_id, incident_id, offense_id, true_offender_person_id   # ML training labels
financial_transactions.csv transaction_id, from_account, to_account, amount, date, linked_person_id, synthetic_pattern
district_socioeconomic.csv district_id, district_name, year, literacy_pct, unemployment_pct, urbanization_pct, sex_ratio, composite_stress_index
crime_stat_aggregate.csv   district_id, year, crime_head, count
```

**Default volumes produced:** 31 districts · 800 persons (160 repeat-offender
pool) · 1500 incidents · 1500 offenses · 2345 role rows · 455 MO-linkage series
rows (130 series) · 208 financial txns · 469 crime-stat rows.

> **Schema mismatch note:** Ananya uses `incident`/flat `offense`/**TEXT** ids;
> the backend uses `case_master`/`act_section_association`/**UUID** ids. The
> `ml_bridge` reconciles them via `id_map.to_uuid()` (deterministic uuid5) and
> `sync_entities.py`. This is the source of the "two person populations" caveat
> in §0.

---

## 12. Per-feature data dependency matrix

What must exist for each capability to return **non-empty, meaningful** output:

| Feature | Hard data requirement | Empty if missing |
|---|---|---|
| **Conversational chat** | Groq key + any queried data | tool returns "no data" |
| **Voice Q&A** | Groq key + audio file (wav/mp3) | — |
| **Conversation → PDF** | an active chat session | — |
| **Network / communities** | ≥300 persons, multi-accused cases, repeat-offender pool | isolated dots, no communities |
| **Centrality (PageRank/betweenness)** | connected co-offending graph in Neo4j | all zeros |
| **Link prediction** | Ananya artifacts + Path-B persons (matching ids) | `links_written: 0` |
| **Hotspot forecast (Hawkes/ETAS)** | cases with lat/long + recent dates, per district/crime_head | flat/empty forecast |
| **MO-linkage** | offenses with mo_text + (Path B) mo_linkage_series labels | no clusters |
| **Sociological** | socio_economic_indicator + crime_stat_aggregate, multi-year | empty charts |
| **GWR map** | ⚠️ **not computed — no code path** | always empty |
| **Risk scoring** | criminal_history + gravity chi_weight + graph centrality | zero/degenerate score |
| **Case brief / timeline** | case_stage_event + documents | sparse brief |
| **Similar-case RAG** | vector_chunk embeddings over real narrative | no matches |
| **Financial crime** | typology-shaped txns, recent dates, < ₹10L structuring | no alerts |
| **RBAC / RLS isolation** | ≥2 districts + district-scoped user | can't demonstrate isolation |
| **Audit trail** | any user actions (auto-logged) | empty log |

---

## 13. Known blockers to "everything working" (must fix to fully test)

1. **Frontend cannot build** — `frontend/src/lib/` (httpClient, types/api,
   hooks/usePermission, hooks/useDebounce, utils, types/permissions,
   authTokenStore) was **never committed**. 91 TS errors. **No UI runs until
   these ~7 modules are created.**
2. **GWR not implemented** — sociological GWR coefficients have no compute path
   (cut in `sociological/correlate.py`). The choropleth GWR widget will be empty.
3. **Two person-identity populations don't converge** (§0) — decide: seed via
   Path A *or* Path B, or make `seed_demo_data.py` set `source_person_id`.
4. **Nothing has been run against a live stack** — all backend/integration
   testing to date is static (import/compile). Only Ananya's ML pipeline is
   empirically green.
5. **`bundle.txt`** (36k lines) is committed noise — unrelated to data, but flag for cleanup.

---

## 14. Runbook — power up & test everything

```bash
# ── 0. Prereqs ────────────────────────────────────────────────
# Postgres+pgvector, Neo4j+GDS, Redis running; env vars set (§1)

# ── 1. Backend + core demo data (Path A) ─────────────────────
cp backend/.env.example backend/.env      # fill SECRET_KEY, *_PASSWORD, GROQ_API_KEY
docker compose up --build                 # api, celery, neo4j, redis, postgres, frontend
docker compose exec api python -m scripts.seed_demo_data
docker compose exec api python -m scripts.seed_financial_transactions   # extra txns

# ── 2. Frontend (BLOCKED until §13.1 fixed) ──────────────────
cd frontend && npm install && npm run build   # currently 91 TS errors

# ── 3. Ananya ML pipeline (Path B) — verified green ──────────
cd ananya-work
# needs: psycopg2-binary faker torch scikit-learn scikit-survival shap node2vec gensim scipy joblib
python -m test_harness.run_harness            # no-Postgres validation of ML logic
# OR full run against a real Postgres per ananya-work/readme.md steps 1-9

# ── 4. Bridge Ananya → backend (Path B integration) ──────────
cd backend
python -m scripts.ml_bridge.sync_entities        --ml-dsn postgresql://crimeportal:crimeportal@localhost/crimeportal
python -m scripts.ml_bridge.sync_graph_and_links --ml-dsn <same>
python -m scripts.ml_bridge.sync_risk_and_mo     --ml-dsn <same>
# NOTE: run these BEFORE relying on ML link/metric data; only lights up Path-B persons

# ── 5. Smoke tests ───────────────────────────────────────────
# API docs:      http://localhost:8090/api/v1/docs
# Metrics:       http://localhost:8090/metrics
# Frontend:      http://localhost:4173   (once build fixed)
# Login:         admin@ksp.demo / Demo@12345  (or SEED_* overrides)
```

---

## 15. Minimum viable demo dataset (if you build only one thing)

To make **every backend feature return something non-trivial**, generate:

- **2+ districts**, full reference tables, **1 user per rank**
- **~500 persons** incl. a **repeat-offender pool (~100)** across multiple cases
- **~800 cases** with lat/long, **recent dates**, multi-accused on many
- **brief_facts narrative** embedded into `vector_chunk`
- **~200 financial txns** shaped into the 3 typologies, recent, sub-threshold structuring
- **31 districts × 3 years** socio + crime aggregates
- Seeded **risk_score / mo_linkage_cluster / predicted_link** rows (or run Path B)

Ananya's `synthetic.py` already produces most of this shape — the gap is loading
it into the **backend** schema (via `ml_bridge`, with the id-mapping caveat),
not Ananya's own.
