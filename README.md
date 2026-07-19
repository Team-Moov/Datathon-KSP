# Karnataka Crime Analytics Platform

**IBM Hackathon — Team Moov**

Intelligent Conversational AI & Crime Analytics Platform for Karnataka Police, with an enterprise
security/governance layer (RBAC, audit trail, immutable change history, MFA, data masking, secure
report sharing) and an Investigator Workspace on top of the core analytics platform.

---

## Overview

A full-stack crime intelligence platform built on:
- **FastAPI** backend with async SQLAlchemy (PostgreSQL + pgvector), Postgres Row-Level Security
  for district-scoped data isolation as a defense-in-depth layer beneath the API's own permission checks
- **Neo4j** graph database for criminal network analysis, with a Redis-backed query cache
- **Groq** (Llama 3.3 70B / 3.1 8B) for conversational AI and case-brief narration, with retry/backoff
  and a distinct "AI unavailable" degraded state — deterministic tool output never disappears when
  narration fails
- **Groq Whisper** for Kannada/English voice transcription
- **Local sentence-transformers embeddings** (all-MiniLM-L6-v2) — no hosted embedding API
- **LangGraph-style** agentic orchestration with deterministic tool dispatch
- **Celery + Redis** for background analytics jobs
- **Vite + React + TypeScript** frontend with a shadcn-style component set and a restrained glass theme

## Architecture Principle

> **The LLM plans and narrates. Deterministic tools compute.**

All analytical capabilities (graph algorithms, Hawkes/ETAS forecasting, risk scoring, financial crime
detection) are fixed, versioned, deterministic tools. The LLM selects and narrates — it never
fabricates a number. See [`karnataka_crime_platform_design.md`](karnataka_crime_platform_design.md)
for the full design record; it is the schema of record for the crime-domain data model.

## Enterprise Security & Governance

- **RBAC** — seven police ranks (Constable → DGP, plus Crime Analyst and Policy Maker specialist
  tracks), expressed as a capability-permission matrix (`backend/app/core/permissions.py`), not a
  single numeric hierarchy. District-wise scoping is enforced twice: once in the API query layer and
  again via Postgres RLS, so a missed permission check at the API layer still can't leak cross-district
  rows.
- **Audit trail** — every login/logout, case view, AI brief generation, report export/download, record
  edit, document upload, and case share is logged with user, IP, device, action, and an optional reason
  (`backend/app/core/audit.py`). Viewable at `/admin/audit-log` (SP/DGP/Policy Maker).
- **Immutable change history** — direct edits to cases/persons are diffed automatically (old value, new
  value, who, when) via a SQLAlchemy event listener, kept separate from the platform's own
  versioned-derived-data pattern (risk scores, predicted links).
- **Optimistic concurrency control** — case/person/note edits carry a `version` field; a stale write
  gets `409 Conflict` instead of silently clobbering a concurrent editor.
- **Simulated MFA** — password + OTP flow with a real refresh-token allowlist (so logout actually
  revokes a session). Delivery is simulated (`ALLOW_MOCK_MFA=true`) until a real SMS/email provider is
  wired in; this must be `false` whenever `ENVIRONMENT=production` — the app refuses to start otherwise.
- **Data masking** — named, per-field masking (never a generic "mask everything" utility) for person
  identity/address fields and the two explicitly sensitive columns the design doc names
  (`PersonCaseRole.religion_id`/`caste_id`).
- **Secure report sharing** — watermarked, optionally password-protected PDF case reports, with
  expiring/download-limited share links.
- **Investigator Workspace** — one aggregated view per case (FIR core fields, evidence, timeline,
  suspects/witnesses, notes, AI brief) at `/cases/:caseId` in the frontend, backed by
  `GET /workspace/cases/{case_id}`.

## Quick Start

`backend/` and `frontend/` are each fully self-contained — their own `Dockerfile`, their own
`.dockerignore`, their own env handling. The root [`docker-compose.yml`](docker-compose.yml) only
composes the two together (via Compose's `include:`) so the whole stack comes up with one command:

```bash
cp backend/.env.example backend/.env
# Fill in at minimum: SECRET_KEY, POSTGRES_PASSWORD, POSTGRES_APP_PASSWORD, NEO4J_PASSWORD, GROQ_API_KEY
# None of these have insecure hardcoded fallbacks — the app refuses to start without them.
docker compose up --build
```

This starts Postgres, Neo4j, Redis, the API, Celery, and an nginx-served production build of the
frontend. `init_db()` runs automatically on API startup: creates tables, runs any pending
`schema_upgrades.py` steps, creates the restricted `app_runtime` Postgres role the API actually
queries through (the RLS policies only apply to a non-owner role — see `backend/app/core/database.py`),
and sets up the RLS policies themselves.

Load demo data (reference lookups, one user per rank, an admin account, and two linked sample cases —
with dates relative to today, not a fixed calendar date, so the financial-crime detection endpoints
actually have something in-window to find):

```bash
docker compose exec api python -m scripts.seed_demo_data
```

| Email | Rank | Purpose |
|---|---|---|
| `admin@ksp.demo` | DGP-tier | **Platform administration** — user management, audit log monitoring. Seeded separately from the rank personas below so "who administers the platform" isn't tangled up with "who plays which officer in the demo." |
| `dgp@ksp.demo` | DGP | Demo persona — Rajendra Holla |
| `sp@ksp.demo` | SP | Demo persona — Meera Nayak |
| `dsp@ksp.demo` | DSP | Demo persona — Arvind Kulkarni |
| `inspector@ksp.demo` | Inspector | Bengaluru-scoped |
| `constable@ksp.demo` | Constable | Bengaluru-scoped |
| `analyst@ksp.demo` | Crime Analyst | |
| `policymaker@ksp.demo` | Policy Maker | Aggregate-only access |

Password for every account is `Demo@12345` by default — **not hardcoded**, it's read from
`SEED_DEMO_PASSWORD`/`SEED_ADMIN_PASSWORD`/`SEED_ADMIN_EMAIL` in `.env` if set, so change those before
seeding anywhere the login list might be guessable. MFA is simulated — the login response includes the
OTP code directly (`simulated_code`) and the frontend surfaces it inline on the verification screen.

- Frontend (containerized production build): `http://localhost:4173`
- API docs: `http://localhost:8090/api/v1/docs`
- Prometheus metrics: `http://localhost:8090/metrics` — see **Monitoring** below

(API published on host port 8090, not 8000 — something else commonly owns 127.0.0.1:8000 on a dev
machine. The frontend's production build is on 4173 — Vite's own conventional "preview build" port —
deliberately different from both the dev server's 5173 and 8080, which tends to already be spoken for
by other local tooling. Container-internal ports are unaffected — only the host-side mappings changed.)

A real `GROQ_API_KEY` (from [console.groq.com](https://console.groq.com)) is required for `/chat` and
`/cases/{id}/brief` to produce real narration — every other endpoint works without one.

### Frontend-only local dev (hot reload)

For active frontend development, run it outside Docker against the same backend for instant HMR:

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`, proxying `/api` to the backend on `:8090` (override via
`VITE_API_PROXY_TARGET` in `frontend/.env` — see `frontend/.env.example` — if your backend runs
somewhere else; never hardcoded past that one fallback). `npm run build` type-checks and produces the
same production bundle the Docker image serves.

## Monitoring

- **Prometheus metrics** — `GET /metrics` (via `prometheus-fastapi-instrumentator`, already wired into
  `backend/app/main.py`) exposes standard HTTP request-count/latency/in-flight metrics for scraping.
- **Audit log** — `GET /admin/audit-log` (SP/DGP/Policy Maker), or the Audit Log page in the frontend —
  every login/logout, case view, edit, export, and share, with user/IP/device/reason.
- **User management** — `GET/POST /admin/users`, `PATCH /admin/users/{id}/role`,
  `POST /admin/users/{id}/deactivate` (DGP-tier only, i.e. `manage_users`) — the `admin@ksp.demo` account
  above is the intended login for this surface.

## Schema Evolution

There are no Alembic migrations yet — `Base.metadata.create_all` (run in `init_db()`) only ever adds
new tables/columns. `backend/app/core/schema_upgrades.py` is a lightweight, numbered, idempotent
stand-in for anything beyond that (a rename, a type change, a backfill). Once the schema stabilizes,
adopting Alembic properly is the recommended next step — the numbered-steps table (`schema_version`)
maps cleanly onto Alembic revisions if that migration is ever made.

## Design Document

See [`karnataka_crime_platform_design.md`](karnataka_crime_platform_design.md) for the full
architecture and feature design — the schema of record for the crime-domain data model.
