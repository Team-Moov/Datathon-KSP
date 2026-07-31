# Deploying on Zoho Catalyst — Integration Plan

**Budget:** ₹2000 credit (~$24) — hackathon/demo scale. Optimise for *fewest
managed services that add real demo value*, not a full cloud re-platform.

**Anchor fact:** the backend is already a clean Dockerized FastAPI app
(`backend/Dockerfile`, uvicorn on :8000, asyncpg + Neo4j + Redis + Groq). That
makes **Catalyst AppSail (custom OCI/Docker runtime)** the natural landing spot —
reuse the existing image almost as-is.

---

## 1. The honest headline: 3 pieces have NO native Catalyst equivalent

Everything else maps cleanly. These three are load-bearing and need a decision:

| Current | Why it doesn't map | Catalyst resolution |
|---|---|---|
| **PostgreSQL `pgvector`** (vector search) | Catalyst Data Store is relational but has **no vector type** | Move embeddings to **QuickML RAG/knowledge base**, OR store vectors in **Stratus/NoSQL** and compute cosine similarity in the AppSail container (keep `sentence-transformers` in-image) |
| **Postgres Row-Level Security** (district isolation) | Data Store has **no RLS** | Drop the DB-level layer; rely on the **app-layer permission checks** (already the primary enforcement in `permissions.py`). You lose the defense-in-depth *second* layer only |
| **Neo4j + GDS** (Louvain, PageRank, betweenness) | Catalyst has **no graph DB / graph algorithms** | Run **networkx in-container** (or a Catalyst Function/Cron job); persist `pagerank/betweenness/community_id` back to Data Store — exactly how Ananya's pipeline already works (`person_graph_metric`) |

> "Catalyst supports all these features" is true for **hosting, storage, compute,
> AI, PDF, auth, jobs** — but *not* for pgvector, RLS, or a graph engine. Plan
> around those three explicitly.

---

## 2. Full service mapping (current stack → Catalyst)

| Current component | Catalyst service | Effort |
|---|---|---|
| FastAPI backend (Docker) | **AppSail** (custom OCI runtime) — reuse `backend/Dockerfile` | Low |
| React SPA frontend | **Web Client Hosting** (or Slate) | Low* |
| Custom domain + SSL | **Domain Mappings** | Trivial |
| API routing / throttling / auth-in-front | **API Gateway** | Low |
| PostgreSQL relational | **Data Store** | **High** (data-layer rewrite) |
| pgvector embeddings | **QuickML RAG** or Stratus/NoSQL + in-app cosine | Med |
| Neo4j graph | networkx in AppSail + Data Store metrics | Med |
| Redis cache | **Cache** | Low |
| Celery + Redis jobs | **Cron** (Cloud Scale) + **Job Scheduling**; **Circuits** for multi-step | Med |
| Document / PDF / audio blobs | **Stratus** (S3-style object storage) | Low |
| Groq LLM (planning/narration) | keep Groq external via **Connections/API Gateway**, OR **QuickML LLM Serving** | Low / Med |
| Groq Whisper (voice) | **Zia Services — speech-to-text / TTS / translation** (native Kannada!) | Low — *upgrade* |
| FIR PDF/OCR ingestion | **Zia Services — OCR / Text Analytics** | Med |
| PDF report + conversation export | **SmartBrowz** (headless browser → PDF), replaces reportlab | Low — *upgrade* |
| Auth + MFA | **Catalyst Authentication** (real MFA), OR keep app JWT | Med |
| Ananya ML models (torch) | bake into AppSail image, OR **QuickML** model hosting / batch **Cron** | Med |
| Early-warning alerts (capability #8) | **Mail** + **Push Notifications** | Low — *new capability* |
| Event-driven ingestion (upload → OCR → extract) | **Signals + Event Functions** | Med |
| CI/CD | **Pipelines** | Low |

*Frontend effort is "Low" *only after* the missing `frontend/src/lib` modules are
created — it currently doesn't build (91 TS errors). Fix that first.

### Things Catalyst gives you *for free* that the design wanted but code lacks
- **Real MFA** (vs. current simulated OTP) → Catalyst Authentication
- **Native Kannada + voice** → Zia speech-to-text + translation (better than the config-only Whisper)
- **Real PDF/report generation** → SmartBrowz
- **Early-warning alerts** (design §8, unimplemented) → Push + Mail + Cron

---

## 3. The one big decision: the database

This is where the ₹2000 / deadline reality bites. Two strategies:

### Strategy A — Catalyst-native Data Store (max credit use, max rework)
- Recreate the schema in **Data Store** (via console/SDK — NOT `create_all`).
- **Rewrite the data layer**: async SQLAlchemy repositories → Catalyst Data Store
  SDK / ZCQL. This is the big-ticket item — every repository and model query.
- pgvector → QuickML RAG; RLS → app-layer only; graph → networkx + metrics table.
- ✅ Fully on-platform, uses the credit, native FT search.
- ❌ Largest rewrite; risky under a deadline; loses pgvector + RLS semantics.

### Strategy B — Lift-and-shift compute, external databases (min rework)
- Deploy the FastAPI container on **AppSail** unchanged.
- Keep **Postgres+pgvector** and **Neo4j** on an **external managed host**
  (e.g. a small managed Postgres + Neo4j Aura free tier). AppSail connects out.
- Use Catalyst only for compute/hosting + the value-add AI services (Zia,
  SmartBrowz, Stratus, Cache, Auth, Cron, Pipelines).
- ✅ Almost no data-layer rework; keeps pgvector + RLS working.
- ❌ Databases aren't on Catalyst (AppSail isn't for stateful DBs); uses less credit.

### Recommended: **Strategy B → C (hybrid), migrate DB later**
For a hackathon with an unbuilt frontend and a never-run backend, **do not
attempt the Data Store rewrite under deadline.** Ship on AppSail with external
Postgres/Neo4j, adopt the high-value native services (Zia voice/OCR, SmartBrowz
PDF, Stratus, Cache, Auth, Cron, Pipelines, Push/Mail), and treat Data Store
migration as a *post-hackathon* item if the platform is pursued.

---

## 4. "DB initialised properly" — what changes

Current `init_db()` (in `core/database.py`) does raw Postgres DDL:
`create_all` → `schema_upgrades` → create `app_runtime` role → install RLS
policies. Behaviour by strategy:

- **Strategy B (external Postgres):** `init_db()` works **unchanged** — point
  `POSTGRES_HOST` at the external DB. pgvector extension + RLS intact. This is
  the seamless path. Run `seed_demo_data` the same way.
- **Strategy A (Data Store):** `init_db()` **does not apply** — Data Store schema
  is created via Catalyst console/SDK; there is no `app_runtime` role and no RLS
  to install. You must reimplement seeding against the Data Store SDK, and move
  district isolation entirely into the app layer.

Either way, **seed order is unchanged** (see `DATA_AND_TESTING_REQUIREMENTS.md`
§2) — reference tables → users → persons → cases → roles → documents/vectors →
financial → aggregates → derived → graph.

---

## 5. Recommended target architecture (Strategy B/C)

```
                    ┌─────────────────── Domain Mappings + SSL ──────────────────┐
                    │                                                             │
  Browser ──► Web Client Hosting (React SPA)   ──►  API Gateway  ──►  AppSail (FastAPI container)
                                                                          │
        ┌───────────────────────────────────────────────┬───────────────┼──────────────┬───────────────┐
        ▼                     ▼                          ▼               ▼              ▼               ▼
  External Postgres     External Neo4j            Catalyst Cache     Stratus       Zia Services     QuickML
  (+pgvector, RLS)      (graph + GDS)             (Redis replace)  (docs/pdf/audio) (STT/TTS/OCR/    (LLM/RAG,
        │                                                                            translation)     optional)
        │                                                                                 │
        └────────── seeded via seed_demo_data (unchanged) ───────────                     ▼
                                                                              (Kannada voice + FIR OCR)

  Background:  Cron + Job Scheduling ──► Hawkes fit / risk rescore / link-prediction / graph-metric recompute
  Events:      Signals + Event Functions ──► on Stratus upload → OCR → extract → embed
  Alerts:      Cron detects → Mail + Push (early-warning, NEW capability)
  CI/CD:       Pipelines ──► build image → deploy AppSail + Web Hosting
```

---

## 6. Phased rollout

1. **Pre-req (blocking):** recreate `frontend/src/lib` so the SPA builds; confirm
   backend runs locally against real Postgres+Neo4j+Redis (it never has).
2. **Compute + hosting:** AppSail (backend image) + Web Client Hosting (frontend)
   + API Gateway + Domain Mappings. Point backend at external Postgres/Neo4j;
   run `init_db()` + `seed_demo_data`.
3. **Swap infra services:** Redis → Cache; local file/PDF → Stratus.
4. **Adopt AI upgrades:** Zia (voice STT/TTS + Kannada translation, FIR OCR);
   SmartBrowz (report + conversation PDF). These *close real design gaps*.
5. **Jobs + events:** Cron/Job Scheduling for analytics recompute; Signals +
   Event Functions for upload→OCR→extract→embed.
6. **New capability:** Push + Mail early-warning alerts (design §8).
7. **Optional:** QuickML for RAG/LLM if dropping Groq; Catalyst Auth for real MFA.
8. **CI/CD:** Pipelines.
9. **Later (post-hackathon):** Strategy-A Data Store migration if pursued.

---

## 7. Budget note (₹2000)
Compute (AppSail), Cache, Stratus, Cron, hosting are cheap at demo scale. The
credit-eaters are **Zia AI calls, QuickML serving, and SmartBrowz** on volume —
fine for a demo, watch them under load testing. Keep Groq external initially to
avoid QuickML serving cost until needed.

---

## 8. Net recommendation
- **Land on AppSail with external Postgres/Neo4j** — smallest path to a running
  system, keeps pgvector + RLS intact, `init_db()`/seeding unchanged.
- **Use Catalyst's AI services to *close design gaps*** (Zia = real Kannada voice;
  SmartBrowz = real PDF; Push/Mail = early-warning) rather than to re-platform
  what already works.
- **Defer the Data Store rewrite** — it's the only "high effort" item and adds no
  demo value under deadline.
- **Fix the frontend build and run the backend live first** — no deployment
  target matters until those two things are true.
