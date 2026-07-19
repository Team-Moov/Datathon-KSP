> ## 📌 This branch: `financial-crime-detection`
>
> Adds working financial crime detection (structuring, funnel/mule accounts,
> layering, organized-cluster detection) on top of Ganesh's schema/stub and
> Vishy's frontend + RLS/permissions rewrite. Rebased cleanly on `Vishy`'s tip,
> zero frontend files touched, zero stale `Role`/`require_roles` references.
>
> **Full writeup — branch structure, what was already there vs. what was
> fixed, the RLS bug found in the seeder, frontend-contract verification —
> is in [`backend/scripts/FINANCIAL_CRIME_README.md`](backend/scripts/FINANCIAL_CRIME_README.md).**
>
> Quick status: code-complete, syntax-checked, logic-validated against
> ground truth (precision 1.0 / recall strong on 2 of 3 typologies) —
> **not yet run against a live Postgres/Neo4j instance**, since nobody on
> the team has started `docker-compose up` yet. That's true repo-wide, not
> specific to this branch.

---

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

## Quick Start (Backend)

```bash
cd backend
cp .env.example .env
# Fill in: SECRET_KEY, POSTGRES_PASSWORD, POSTGRES_APP_PASSWORD, NEO4J_PASSWORD, GROQ_API_KEY
docker compose up --build
```

`init_db()` runs automatically on API startup: creates tables, runs any pending
`schema_upgrades.py` steps, creates the restricted `app_runtime` Postgres role the API actually
queries through (the RLS policies only apply to a non-owner role — see `app/core/database.py`), and
sets up the RLS policies themselves.

Load demo data (reference lookups, one user per rank, two linked sample cases with a real
co-offending + financial-transaction chain so the network explorer and financial-crime pages aren't
empty):

```bash
docker compose exec api python -m scripts.seed_demo_data
```

Demo login for every rank — password `Demo@12345`:

| Email | Rank |
|---|---|
| `dgp@ksp.demo` | DGP |
| `sp@ksp.demo` | SP |
| `dsp@ksp.demo` | DSP |
| `inspector@ksp.demo` | Inspector (Bengaluru-scoped) |
| `constable@ksp.demo` | Constable (Bengaluru-scoped) |
| `analyst@ksp.demo` | Crime Analyst |
| `policymaker@ksp.demo` | Policy Maker |

MFA is simulated — the login response includes the OTP code directly (`simulated_code`) and the
frontend surfaces it inline on the verification screen.

API docs: `http://localhost:8090/api/v1/docs`

(Published on host port 8090, not 8000, in case something else on your machine
already owns 8000 — the container's internal port is still 8000; only the
`docker-compose.yml` host mapping changed.)

A real `GROQ_API_KEY` (from [console.groq.com](https://console.groq.com)) is required for `/chat` and
`/cases/{id}/brief` to produce real narration — every other endpoint works without one.

## Quick Start (Frontend)

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:5173`, proxying `/api` to the backend on `:8090` (see `vite.config.ts`).
`npm run build` type-checks and produces a production bundle.

## Schema Evolution

There are no Alembic migrations yet — `Base.metadata.create_all` (run in `init_db()`) only ever adds
new tables/columns. `backend/app/core/schema_upgrades.py` is a lightweight, numbered, idempotent
stand-in for anything beyond that (a rename, a type change, a backfill). Once the schema stabilizes,
adopting Alembic properly is the recommended next step — the numbered-steps table (`schema_version`)
maps cleanly onto Alembic revisions if that migration is ever made.

## Design Document

See [`karnataka_crime_platform_design.md`](karnataka_crime_platform_design.md) for the full
architecture and feature design — the schema of record for the crime-domain data model.
