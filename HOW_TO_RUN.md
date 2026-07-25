# How to run the whole thing end-to-end

Full path from a fresh machine to a working app in the browser, with real
(synthetic) financial crime data loaded. Written for Windows without Docker
Desktop pre-installed — uses WSL2 + Docker Engine instead, which doesn't
need Windows admin rights.

---

## 0. Status check — known blockers (as of this branch)

**Fixed, no longer an issue:** `frontend/src/lib/api/httpClient.ts` was
missing earlier (every `*Api.ts` file imports it, `npm run dev` would fail
to build) — confirmed this is now present on `vishy-catalyst`/`master`. If
you're running from a much older branch and hit a build error naming this
file, that's why.

**Still true:** nothing in the entire repo has been run against a live
database by anyone on the team as of the last check. This guide is the
first attempt.

---

## 1. Prerequisites

- **WSL2 with Ubuntu** (check with `wsl --status` in cmd/PowerShell — if you
  don't have it, `wsl --install` needs admin rights once; skip this doc's
  approach and use Docker Desktop instead if you can't get admin access)
- Node.js (for the frontend, only if running it outside Docker)
- That's it — Docker itself gets installed *inside* WSL in step 2, which
  only needs your Linux user's own `sudo` password, not Windows admin.

---

## 2. Install Docker inside WSL (one-time)

Open a WSL terminal (type `wsl` in cmd) and run:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

---

## 3. Get to the repo and set up environment variables

WSL sees your Windows drives under `/mnt/` — so `D:\datathonKSRTC\repo`
becomes:

```bash
cd /mnt/d/datathonKSRTC/repo
cp backend/.env.example backend/.env
```

Now **edit `backend/.env`** (`nano backend/.env`, or open it in VS Code) —
these four have **no default and the app refuses to start without them**,
everything else in `.env.example` already works as-is:

```
SECRET_KEY=your-own-password-here
POSTGRES_PASSWORD=your-own-password-here
POSTGRES_APP_PASSWORD=your-own-password-here
NEO4J_PASSWORD=your-own-password-here
```

(Any value works — this only runs on your own machine. Leave
`GROQ_API_KEY` blank; it has a safe empty default and is only needed for
the `/chat` AI features, not financial crime detection.)

---

## 4. Start everything

From the repo root (not `backend/`):

```bash
docker compose up --build
```

This one command builds and starts: Postgres (with pgvector), Neo4j (with
the graph-data-science plugin), Redis, the FastAPI backend, Celery
worker+beat, and an nginx-served production build of the frontend.

First run takes a few minutes (building images). The API creates its own
database tables and Row-Level Security policies automatically on startup —
no manual migration needed for a fresh database.

**Check it's actually up** (in a second WSL terminal):
```bash
curl http://localhost:8090/api/v1/docs
```
Or just open that URL in a browser — it's the FastAPI Swagger UI.

---

## 5. Load the data — both seeders

Nothing exists in the database until these run. In a second terminal
(leave `docker compose up` running in the first):

```bash
cd /mnt/d/datathonKSRTC/repo/backend

# Named, walkable demo data — 2 people (Manjunath Gowda, Naveen Reddy)
# with hand-picked structuring/funnel/layering patterns and matching
# risk-profiling scores. Good for pointing at something specific live.
docker compose exec api python -m scripts.seed_demo_data

# Bulk, realistic dataset — 600+ typology-driven synthetic transactions.
# This is the actual validated pipeline (precision/recall proof), not a
# curated highlight reel. Adds to the same table, doesn't overwrite the above.
docker compose exec api python -m scripts.seed_financial_transactions
```

Optional — get real accuracy numbers off the bulk data:
```bash
docker compose exec api python -m scripts.validate_financial_crime
```

---

## 6. Open the app and see it work

- **Frontend:** `http://localhost:4173`
- **API docs:** `http://localhost:8090/api/v1/docs`

Log in with a demo account (all created by `seed_demo_data.py`). Password
is whatever you set `SEED_DEMO_PASSWORD` to in your own `backend/.env` —
defaults to `Demo@12345` if you didn't set it (see `.env.example`):

| Email | Rank |
|---|---|
| `dsp@ksp.demo` | DSP |
| `analyst@ksp.demo` | Crime Analyst |

(Financial data specifically requires DSP/SP/DGP/CRIME_ANALYST — lower
ranks won't see the Financial Crime page's data even if the page loads.)

Open the case `THEFT-BLR-INDR-2025-0142` or go straight to the Financial
Crime Detection page:
- **Structuring** tab — Manjunath Gowda's pattern, or look up any account
  from the bulk data (`SELECT DISTINCT from_account FROM financial_transaction LIMIT 5;`
  against Postgres if you want a bulk-data example instead)
- **Funnel Account** tab — Naveen Reddy's mule-account pattern
- **Layering Cycles** tab — loads automatically, shows every detected loop
  (including Naveen Reddy's, which was specifically built to close a loop
  so this detector would actually find it)

`/organized-clusters` and `/scan` endpoints work but aren't wired to any
UI tab yet — reachable via the Swagger docs (`/api/v1/docs`) if you want to
show them without a dedicated page.

---

## Quick reference — ports

| Service | Port | What it's for |
|---|---|---|
| Frontend (production build) | 4173 | The actual app in your browser |
| Backend API | 8090 | REST API, Swagger docs at `/api/v1/docs` |
| Postgres | 5432 | Relational data |
| Neo4j Bolt | 7687 | Graph queries (used by the app) |
| Neo4j Browser | 7474 | Neo4j's own web UI, for manually poking the graph |
| Redis | 6379 | Celery broker/backend |

---

## If something's not working

- **`docker compose up` fails on `sudo` / permission errors** → you skipped
  `newgrp docker` in step 2, or need to fully close and reopen the WSL
  terminal after the `usermod` command.
- **API container won't start / health check fails** → check
  `docker compose logs api` — usually a missing/wrong `.env` value (the
  four with no defaults, from step 3).
- **Financial data seeder finds "no CaseMaster/Person rows" every time you
  run it** → it should be using the admin DB connection specifically to
  get around Postgres Row-Level Security on `case_master`. If it's not,
  something regressed — see `backend/scripts/FINANCIAL_CRIME_README.md`.
- **Frontend loads but Financial Crime page shows nothing** → confirm
  you're logged in as DSP/SP/DGP/CRIME_ANALYST, not a lower rank, and that
  step 5's seeders actually ran without error.
- **Port already in use** → something else on your machine owns that port;
  check `docker compose ps` and either stop the conflicting service or
  change the port mapping in `docker-compose.yml`.
