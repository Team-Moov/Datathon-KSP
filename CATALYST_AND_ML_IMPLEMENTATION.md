# Catalyst Integration & ML Pipeline — Implementation Record

Branch: **`catalyst`**. This documents everything implemented in the Catalyst
integration and ML-connection work: what was built, how it works, what was fixed,
and how it was verified (every item below was tested live against the running stack,
not just written).

---

## 1. The design principle: provider abstractions (Catalyst is opt-in)

Every Catalyst integration sits behind a **provider interface with a local default**,
selected by a config flag. This means teammates run fully local (no Catalyst
credentials), while the demo runs on Catalyst — a one-line `.env` flip per service,
no code changes at call sites.

| Concern | Interface | Flag | Local default | Catalyst option |
|---|---|---|---|---|
| Object storage | `StorageProvider` | `STORAGE_PROVIDER` | `local` (filesystem) | `catalyst_stratus` |
| Cache | `CacheProvider` | `CACHE_PROVIDER` | `redis` | `catalyst` |
| PDF rendering | `PdfRenderer` | `PDF_PROVIDER` | `local` (xhtml2pdf) | `smartbrowz` |
| OCR | `OcrProvider` | `OCR_PROVIDER` | `local` (digital-PDF text) | `zia` |
| NER | `NlpProvider` | `NLP_PROVIDER` | `local` (spaCy) | `zia` |

Shared auth lives in `app/core/catalyst_auth.py` — a single OAuth token manager
(refresh-token → access-token, cached) reused by every REST-based Catalyst adapter.
All adapters use **REST + OAuth** (not the `zcatalyst-sdk`, which only self-authenticates
inside Catalyst) so the *same* code works from local Docker **and** on AppSail.

---

## 2. Catalyst services integrated (all tested live)

### 2.1 Stratus — object storage  ✅
- **Files:** `app/core/storage/{base,local,stratus,__init__}.py`
- **What:** document/report/audio blobs. Uploads now land in the Catalyst `crime`
  bucket (India DC). Refs are self-describing: `local://…`, `seed://…`, `stratus://…`.
- **Endpoint pattern:** per-bucket domain `https://crime-development.zohostratus.in/<key>`
  (S3-style PUT/GET/DELETE).
- **Verified:** upload via API → `stratus://documents/…`, byte-roundtrip, delete → 404.

### 2.2 Cache — Redis ↔ Catalyst Cache  ✅
- **Files:** `app/core/cache/{base,redis_cache,catalyst_cache,__init__}.py`; cut over
  `app/core/graph_db.py`.
- **What:** graph-query cache. Namespace-based with **version-counter invalidation**
  (works on both backends; no prefix-scan needed, which Catalyst Cache can't do).
- **Catalyst quirks handled:** `expiry_in_hours` capped 1–48; `cache_name` length-limited
  (~50 chars → hashed to a 40-char digest); POST upserts (no UPDATE scope needed);
  segment auto-discovered.
- **Verified:** both backends set/get/upsert/invalidate; `/network/co-offending` caches
  through Catalyst Cache end-to-end.

### 2.3 Zia OCR — scanned image → text  ✅
- **Files:** `app/core/ocr/{base,local_ocr,zia,__init__}.py`; endpoint `POST /documents/ocr`.
- **What:** real OCR of scanned images/handwriting (docling/spaCy can't). **10 Indian
  languages** (scanned Kannada FIRs → searchable text). Local fallback reads digital PDFs only.
- **Endpoint:** `POST {api}/baas/v1/project/{id}/ml/ocr`, multipart `image`, scope `mlkit.READ`.
- **Verified:** image → `{"text":"FIRNo 12345-Theft near MG Road Bengaluru…","confidence":97,"provider":"zia"}`.

### 2.4 Zia NER — text → entities  ✅
- **Files:** `app/core/nlp/{base,local_nlp,zia_nlp,__init__}.py`.
- **What:** entity extraction. Local = spaCy `en_core_web_sm`; Catalyst = Zia
  text-analytics NER. Normalized to `[{text, type}]`.
- **Endpoint:** `POST {api}/baas/v1/project/{id}/ml/text-analytics/ner`, JSON `{"document":[…]}`.
- **Wired into ingestion** (see §4).

### 2.5 SmartBrowz — HTML → PDF  ✅
- **Files:** `app/core/pdf/{base,local_renderer,smartbrowz,__init__}.py`; reports rewritten
  as HTML in `app/services/report_service.py`.
- **What:** case-report and conversation-transcript PDFs, rendered by real headless
  Chromium (richer than local xhtml2pdf). Case report ~30 KB via SmartBrowz vs ~3 KB local.
- **Endpoint:** `POST {api}/browser360/v1/project/{id}/convert`, body
  `{"output_options":{"output_type":"pdf"},"html":…}`, scope `pdfshot`/`dataverse`.
- **Gotcha:** needed **console enablement** of the SmartBrowz component (the 401 was a
  dormant component, not a scope problem). Once enabled → worked.
- **Verified:** `/reports/cases/{id}/export` and `/chat/export` both return valid PDFs.

### 2.6 Auth token scopes
One self-client refresh token carries the full scope set:
`Stratus.* , ZohoCatalyst.buckets.* , cache.* , segments.ALL , pdfshot.execute ,
dataverse.execute , mlkit.READ`. India DC (`accounts.zoho.in` / `api.catalyst.zoho.in`).

---

## 3. ML pipeline integration (Ananya's models → backend)

**Problem:** Ananya's ML pipeline (`ananya-work/`) was a standalone island on a
different schema (§3.1 draft, TEXT ids) than the backend (§3.4 real-KSP, UUID ids),
connected only by an untested, no-op bridge.

**Solution — no schema change.** The `ml_bridge` reads Ananya's output and writes into
the backend's existing tables, mapping her TEXT ids → backend UUIDs deterministically
(`uuid5`), tagging `source_person_id`.

**What was made to work:**
- `scripts/ml_bridge/ml_conn.py` — **new**: dual-source connection (SQLite harness
  output *or* Postgres) + date-string parsers (SQLite returns dates as strings; asyncpg
  needs objects).
- `sync_entities` / `sync_risk_and_mo` / `sync_graph_and_links` — patched to the
  dual-source helper; fixed a Postgres-only `DISTINCT ON` → portable JOIN; added
  `graph_db.connect()` for standalone runs.

**Result (loaded into the backend, verified via API):**
| Ananya model output | Backend landing | Count |
|---|---|---|
| Persons / cases / roles / financial | `person` (`source_person_id`), `case_master`, … | 800 / 1500 / … |
| **Link prediction** (node2vec+logreg) | Neo4j `predicted_link` | 100 — surfaced via `/network/predicted-links/` |
| **Risk scores** (survival RSF) | `risk_score` | 606 |
| **MO-linkage clusters** (Siamese) | `mo_linkage_cluster` | 1500 |
| Graph metrics (PageRank/betweenness/community) | Neo4j | 208 |

---

## 4. Data-gap enrichment (`scripts/ml_bridge/enrich.py` — new)

The bridge left analytics empty/sparse; one idempotent pass closed it:
- **31 districts** created (the bridge previously had only 2 to map to → most cases had `district_id=NULL`).
- **1500 cases geo-tagged** with deterministic Karnataka-bbox coords, clustered per
  district (clearly synthetic — never real crime-scene coordinates).
- **2345 `ACCUSED_IN` co-offending edges + person names** pushed to Neo4j.
- **31 socio + 469 crime-stat** rows synced.

Plus **`scripts/embed_cases.py`** (new): batch-embedded **1502 case narratives** into
`vector_chunk` — the pgvector store was empty (0 rows); now similar-case RAG works.

**Ingestion pipeline wired** (`ingestion_service.py`): upload → Stratus → classify →
**Zia OCR** (images) → **Zia/​spaCy NER** → embed → **pgvector** → similar-case RAG.

---

## 5. Bug fixes (found by actually running with data)

| # | Bug | Fix |
|---|---|---|
| 1 | `person_match_candidate.reviewed_by` FK → `users.id` but table is `user` — broke `create_all` (schema never executed) | → `user.id` |
| 2 | `torch` pinned to CUDA build → ~2.5 GB unused NVIDIA libs, 7 GB+ image | `torch==2.3.1+cpu` + CPU index |
| 3 | `_similar_cases` async lazy-load on `chargesheet` (`MissingGreenlet`) — only surfaced once pgvector had data | eager-load via `selectinload` |
| 4 | `/network/communities` 500 — GDS projection references a non-existent edge type; also GDS-only (Aura Free lacks it) | rewrote to **networkx Louvain** (GDS-free) |
| 5 | `/trends/hotspots` 500 — code did `str(date)`, breaking asyncpg date binding | bind the `date` object + defensive coercion |
| 6 | `/trends/hotspots` 500 — Postgres `Numeric` → `Decimal`, numpy trig can't consume | cast lat/long to `float` |
| 7 | predicted-links `name: null` — Neo4j nodes had no name property | enrichment sets `p.name` on nodes |
| 8 | `init_groq()` hard-fails startup without `GROQ_API_KEY` despite README saying optional | documented (placeholder boots the app) |
| 9 | `_get_mo_escalation` was a placeholder returning 0.0 | real CHI-escalation query (prior commit) |

**Non-bugs confirmed working-as-designed:** risk `422` = the §7.3 fairness gate
(blocks unverified criminal history); `persons/search 422` = min-length validation.

---

## 6. Robustness verification

Full endpoint sweep against the rich data — **all green**:
`/cases`, `/persons/search`, `/network/{co-offending,communities,ego,predicted-links,multi-jurisdiction}`,
`/risk/{id}/compute`, `/financial/*`, `/trends/hotspots`, `/socio/indicators`, `/workspace/*`.

All three DB types are now genuinely exercised:
- **Relational (Postgres):** 1502 cases, 800+ persons, 606 risk scores, 1500 MO clusters
- **Vector (pgvector):** 1502 embeddings → similar-case RAG returns semantic matches
- **Graph (Neo4j):** 2345 co-offending edges + 100 predicted links + 34 communities

---

## 7. Frontend wiring

- **Conversation → PDF export** button added to the Investigator Assistant
  (`chatApi.ts` → `useChatSession` → `InvestigatorAssistantPage.tsx`) → `POST /chat/export`.
- ML endpoints (predicted-links, risk) were already consumed by the network/risk pages —
  they now surface Ananya's data automatically.
- Frontend builds clean (`tsc -b && vite build`); the earlier missing `src/lib` was a
  `.gitignore` bug, fixed on `catalyst`.

---

## 8. Deployment status & the AppSail constraint

**Target:** backend → Catalyst **AppSail**, frontend → **Web Client Hosting**, DBs
external (AppSail can't host Postgres/Neo4j), Redis → Catalyst Cache.

**Blocker found:** AppSail caps at **2 GB RAM** (options 128/256/512/1024/2048). The
current image is **5.85 GB** and loading `torch`+`transformers`+`sentence-transformers`
pushes RAM toward the ceiling. **To deploy on AppSail the backend must be slimmed:**
- swap `sentence-transformers` (torch, ~1 GB RAM) → `fastembed` (ONNX, ~200 MB), same model;
- drop `spaCy`/`docling`/`unstructured` (OCR+NER now on Zia), `mgwr`/`geopandas` (GWR unused).
- → image ~1–1.5 GB, RAM < 1 GB → fits AppSail.

**Prerequisite (user-side):** external Postgres+pgvector (Neon / GCP Cloud SQL) and
Neo4j (Aura / GCP VM). Then: push slimmed image → AppSail, frontend → Web Hosting, wire env.

---

## 9. Config flags (all in gitignored `backend/.env`)

```
STORAGE_PROVIDER=local|catalyst_stratus
CACHE_PROVIDER=redis|catalyst
PDF_PROVIDER=local|smartbrowz
OCR_PROVIDER=local|zia
NLP_PROVIDER=local|zia
CATALYST_DC=in
CATALYST_PROJECT_ID / CLIENT_ID / CLIENT_SECRET / REFRESH_TOKEN
STRATUS_BUCKET / STRATUS_BASE_URL
```

## 10. Reproduce (rich data)
```
docker compose up -d
docker compose exec api python -m scripts.seed_demo_data
docker compose cp ananya-work/test_harness/test.db api:/tmp/ml_source.db
# run bridge sync_entities → sync_risk_and_mo → sync_graph_and_links → enrich  (see TEAM_SETUP.md)
docker compose exec api python -m scripts.embed_cases
```

---

## 11. Outstanding
- **Backend slim-down for AppSail** (§8) — the critical path to "deployed on Catalyst".
- **External DB provisioning** (Neon + Aura, or GCP).
- **Rotate the Catalyst Client Secret** (exposed during setup) + re-mint one final token.
- Optional: forecast top-N cap for the UI; wire Zia NER entities into entity resolution;
  Catalyst RAG as a separate document-Q&A feature; voice input UI (`/chat/voice` exists).
