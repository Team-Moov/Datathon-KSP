# Team Setup — Running the Platform on Your Machine

Branch: **`catalyst`**. This covers running the full stack locally, with or without
the Zoho Catalyst services.

## The key idea: Catalyst is opt-in

Every Catalyst integration sits behind a provider flag with a **local default**:

| Concern | Flag (in `backend/.env`) | Local default | Catalyst |
|---|---|---|---|
| Object storage | `STORAGE_PROVIDER` | `local` (filesystem) | `catalyst_stratus` |
| Cache | `CACHE_PROVIDER` | `redis` | `catalyst` |
| PDF | `PDF_PROVIDER` | `local` (xhtml2pdf) | `smartbrowz` |

**So a teammate can run the entire app with zero Catalyst credentials** — everything
works on the local providers. Catalyst is only needed to *test the Catalyst path*.

---

## Mode A — Fully local (no Catalyst secrets needed) ← most teammates

```bash
git clone <repo> && cd IBM_Hackathon && git checkout catalyst

# 1. Backend env — copy the example and fill the non-Catalyst secrets
cp backend/.env.example backend/.env
#   Set: SECRET_KEY, POSTGRES_PASSWORD, POSTGRES_APP_PASSWORD, NEO4J_PASSWORD
#   Set: GROQ_API_KEY (real key → chat works; any non-empty value → app boots, chat disabled)
#   Leave provider flags unset/default → local, redis, local  (NO Catalyst creds required)

# 2. Bring up the stack (Docker Desktop must be running)
docker compose up --build          # postgres+pgvector, neo4j, redis, api, celery, frontend

# 3. Seed demo data
docker compose exec api python -m scripts.seed_demo_data

# 4. Use it
#   API docs:  http://localhost:8090/api/v1/docs
#   Frontend:  http://localhost:4173   (containerized build)
#   Login:     admin@ksp.demo / Demo@12345
```

Frontend hot-reload dev (optional, instead of the container):
```bash
cd frontend && npm install && npm run dev     # http://localhost:5173, proxies /api → :8090
```

---

## Mode B — With Catalyst services (Stratus / Cache / SmartBrowz)

Needs the Catalyst credentials for **Project-Rainfall**. These are **shared** (one
project, one self-client) — get the values from the project owner and paste into
your `backend/.env` (it is gitignored — never commit it):

```
STORAGE_PROVIDER=catalyst_stratus     # or leave local
CACHE_PROVIDER=catalyst               # or leave redis
PDF_PROVIDER=smartbrowz               # once SmartBrowz is enabled (see console below)
STRATUS_BUCKET=crime
STRATUS_BASE_URL=https://crime-development.zohostratus.in
CATALYST_DC=in
CATALYST_PROJECT_ID=54726000000013024
CATALYST_CLIENT_ID=<shared>
CATALYST_CLIENT_SECRET=<shared>
CATALYST_REFRESH_TOKEN=<shared>       # minted with the full scope set
```

**Share `backend/.env` over a secure channel** (password manager / DM), not git.
The refresh token works from any machine (it's project-scoped, not per-device).

> If a teammate wants their *own* credentials instead of sharing: create a Self
> Client at `api-console.zoho.in`, generate a token with the scope string in
> `DEPLOYMENT_ZOHO_CATALYST.md`, exchange for a refresh token, and use their values.

---

## Loading the ML data (Ananya's models → backend)

The demo seed has only a few persons. To load Ananya's 800-person synthetic
dataset **with her model outputs** (predicted links, survival risk, MO clusters),
run her pipeline then the bridge:

```bash
# 1. Produce Ananya's output (SQLite, via the no-Postgres harness)
cd ananya-work && pip install faker torch scikit-learn scikit-survival shap node2vec gensim scipy joblib
python -m test_harness.run_harness          # writes ananya-work/test_harness/test.db

# 2. Copy that db into the api container and run the bridge
cd .. && docker compose cp ananya-work/test_harness/test.db api:/tmp/ml_source.db
docker compose exec api python - <<'PY'
import asyncio
from scripts.ml_bridge import sync_entities, sync_risk_and_mo, sync_graph_and_links
async def main():
    await sync_entities.run('/tmp/ml_source.db')
    await sync_risk_and_mo.run('/tmp/ml_source.db')
    await sync_graph_and_links.run('/tmp/ml_source.db', None)
asyncio.run(main())
PY
```

After this, `/network/predicted-links/{id}` and risk scores show Ananya's model
output for her 800 persons (ids mapped deterministically, so re-runs are safe).

---

## Ports & the override file (read this if `docker compose up` fails to bind)

Default host ports: **8090** (api), **5432** (postgres), **7687**/**7474** (neo4j),
**6379** (redis), **4173** (frontend). If one is already taken on your machine,
create a local **`docker-compose.override.yml`** (gitignored — each machine has its
own) to remap just the host side. Example (postgres 5432 was taken):

```yaml
name: karnataka-crime-platform
services:
  postgres:
    ports:
      - "5433:5432"
```

The app talks to the DBs over the container network, so host remaps don't affect it.

---

## Gotchas
- **Docker Desktop must be running** before `docker compose`.
- **First build is large** (~5.8 GB — the ML stack). `torch` is pinned to the CPU
  wheel, so it works on any machine (no GPU needed) and skips ~2.5 GB of CUDA libs.
- **`GROQ_API_KEY` is required to boot** even for non-chat features (the app hard-checks
  it at startup) — use a real key, or any non-empty placeholder to boot with chat disabled.
- **`backend/.env` is gitignored** — never commit secrets. Share it out-of-band.
