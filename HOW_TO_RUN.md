# How to run the whole thing end-to-end

For anyone connecting the frontend to the backend (or just trying to see
the financial crime detection actually work) — this is the full path from
zero to a working app in the browser.

---

## 0. Known blocker — fix this first

**`frontend/src/lib/api/httpClient.ts` does not exist**, even though every
single `*Api.ts` file (`financialApi.ts`, `adminApi.ts`, `authApi.ts`, ...)
imports it. Confirmed by checking the actual file tree — it was never
added. `npm run dev` will fail to build until this file exists.

This isn't a financial-crime-module problem — it blocks the whole frontend.
Whoever owns the API client layer needs to add it before step 4 below will
work for anyone.

---

## 1. Prerequisites

- Docker Desktop installed and running
- Node.js (for the frontend)
- Python 3.11+ with the packages in `backend/requirements.txt` (only needed
  if you want to run scripts like the seeder outside the `api` container)

---

## 2. Set up environment variables

```bash
cd backend
cp .env.example .env
```

The defaults in `.env.example` work out of the box for local/demo use
**except** `GROQ_API_KEY` — that's only required for the `/chat` and
case-brief AI features (get one free at console.groq.com). Financial
crime detection does not need it.

---

## 3. Start everything with Docker

```bash
cd backend
docker-compose up -d
```

This starts, in one command:
- **PostgreSQL** (`pgvector/pgvector:pg16`) — port `5432`
- **Neo4j** (with the graph-data-science plugin) — bolt on `7687`, browser UI on `7474`
- **Redis** — port `6379`
- **The FastAPI backend itself** — published on **`http://localhost:8090`**
  (not 8000 — see the comment in `docker-compose.yml`, something else on
  dev machines may already own port 8000)
- Celery worker + beat, for background jobs

The API creates its own tables and Row-Level Security policies
automatically on first startup (`init_db()` in `app/main.py`'s lifespan
handler) — no manual migration step needed for a fresh database.

Check it's actually up:
```bash
docker-compose ps
curl http://localhost:8090/api/v1/docs
```
(Or open that URL in a browser — it's the FastAPI Swagger UI.)

---

## 4. Populate real data

Nothing exists in the database until something seeds it. Two seeders exist:

```bash
# From inside the backend/ directory, or via docker-compose exec api ...

# Baseline demo data — a handful of linked sample cases, users per rank,
# so pages aren't empty on a fresh install
python -m scripts.seed_demo_data

# The financial crime module specifically — bulk typology-driven synthetic
# transactions (structuring, funnel, layering) with real detection-ready data
python -m scripts.seed_financial_transactions
```

Run demo data first if you want guaranteed minimal content everywhere;
run the financial seeder for the realistic bulk dataset the detectors were
actually built and validated against.

To confirm detection works against what got seeded:
```bash
python -m scripts.validate_financial_crime
```

---

## 5. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Vite's dev server automatically proxies any `/api/*` request to
`http://localhost:8090` (see `frontend/vite.config.ts`) — so once both the
backend and frontend are running, the app in your browser talks to the
real backend with no extra config.

---

## 6. Actually seeing the financial crime page work

Once logged in (demo users are created by `seed_demo_data.py` — check that
script for exact emails/passwords, DSP/SP/DGP/CRIME_ANALYST roles are the
ones with `VIEW_FINANCIAL_RAW` permission), go to the Financial Crime
Detection page. It has three tabs:

- **Structuring** / **Funnel Account** — type an account identifier and
  click "Check account." You need a real account number from the seeded
  data — query Postgres directly to find one:
  ```sql
  SELECT DISTINCT from_account FROM financial_transaction LIMIT 5;
  ```
- **Layering Cycles** — loads automatically, no input needed, shows every
  detected cycle in the seeded data.

The `/organized-clusters` and `/scan` endpoints exist and work
(`app/api/v1/endpoints/financial.py`) but aren't wired into the UI yet —
they'd need a new tab/page if you want that visible in a demo.

---

## Quick reference — ports

| Service | Port | What it's for |
|---|---|---|
| Backend API | 8090 | REST API, Swagger docs at `/api/v1/docs` |
| Frontend dev server | 5173 | The actual app in your browser |
| Postgres | 5432 | Relational data |
| Neo4j Bolt | 7687 | Graph queries (used by the app) |
| Neo4j Browser | 7474 | Neo4j's own web UI, for manually poking the graph |
| Redis | 6379 | Celery broker/backend |

---

## If something's not working

- **`npm run dev` fails immediately** → almost certainly the missing
  `httpClient.ts` from section 0. Check with whoever owns the API client
  layer.
- **Financial data seeder finds "no CaseMaster/Person rows" every time you
  run it** → it should be using the admin DB connection specifically to
  get around Postgres Row-Level Security on `case_master`. If it's not,
  something regressed — see `backend/scripts/FINANCIAL_CRIME_README.md`
  for the full explanation of why this matters.
- **API container won't start / health check fails** → check
  `docker-compose logs api` — usually a missing/wrong `.env` value.
- **Nothing loads at all in the frontend** → confirm both
  `docker-compose ps` (backend/DB containers) and `npm run dev` (frontend)
  are actually running at the same time, in two separate terminals.
