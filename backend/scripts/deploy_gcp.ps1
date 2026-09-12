# ═══════════════════════════════════════════════════════════════════════════
# End-to-end GCP backend deployment — Karnataka Crime Analytics Platform
# Run these phases in order from a PowerShell prompt. Each phase is
# independent — re-run a single phase if it fails partway through; gcloud
# create commands error out harmlessly if the resource already exists.
# ═══════════════════════════════════════════════════════════════════════════

# ── Variables (edit these once, reused everywhere below) ─────────────────────
$PROJECT      = "karnataka-crime-analytics"
$REGION       = "us-central1"
$SQL_INSTANCE = "karnataka-crime-db"
$SQL_CONN     = "$PROJECT`:$REGION`:$SQL_INSTANCE"   # full Cloud SQL connection name
$REDIS_NAME   = "karnataka-crime-redis"
$REPO         = "backend"
$IMAGE        = "$REGION-docker.pkg.dev/$PROJECT/$REPO/api:latest"
$BUCKET       = "$PROJECT-uploads"
$DB_NAME      = "karnataka_crime"

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 0 — Auth & project selection
# ═══════════════════════════════════════════════════════════════════════════
gcloud auth login
gcloud config set project $PROJECT
gcloud config set account <your-gcp-account-email>   # e.g. vishalhateswork@gmail.com

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1 — Enable required APIs (safe to re-run; no-ops if already enabled)
# ═══════════════════════════════════════════════════════════════════════════
gcloud services enable `
  run.googleapis.com sqladmin.googleapis.com `
  artifactregistry.googleapis.com secretmanager.googleapis.com `
  cloudscheduler.googleapis.com vpcaccess.googleapis.com `
  redis.googleapis.com cloudbuild.googleapis.com storage.googleapis.com `
  --project $PROJECT

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2 — Artifact Registry + build & push the backend image
# ═══════════════════════════════════════════════════════════════════════════
gcloud artifacts repositories create $REPO --repository-format=docker `
  --location=$REGION --project $PROJECT --description="Karnataka Crime backend images"

# Run from the repo root (so the build context is backend/):
gcloud builds submit backend/ --tag $IMAGE --project $PROJECT

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3 — Cloud SQL: Postgres 16 + pgvector
# (Already created in this project as of this session — skip create if so;
#  `gcloud sql instances list --project $PROJECT` to check first.)
# ═══════════════════════════════════════════════════════════════════════════
gcloud sql instances create $SQL_INSTANCE `
  --database-version=POSTGRES_16 --edition=ENTERPRISE --tier=db-custom-2-8192 `
  --region=$REGION --storage-size=20 --storage-auto-increase --project $PROJECT

gcloud sql databases create $DB_NAME --instance=$SQL_INSTANCE --project $PROJECT

# Set passwords — pick strong values and remember them, they go into Secret
# Manager in Phase 6. $env: vars here are just scratch space for this shell.
$env:PG_ADMIN_PW = "<CHOOSE-A-STRONG-PASSWORD>"
gcloud sql users set-password postgres --instance=$SQL_INSTANCE `
  --password=$env:PG_ADMIN_PW --project $PROJECT

# init_db() creates the app_runtime role + RLS policies automatically on
# first app startup (Phase 8) — you don't create that role by hand. But the
# pgvector extension itself must exist before init_db()'s CREATE TABLE with
# a vector column runs, so do it now via an interactive psql session:
gcloud sql connect $SQL_INSTANCE --user=postgres --database=$DB_NAME --project $PROJECT
# -> at the psql prompt, paste:
#      CREATE EXTENSION IF NOT EXISTS vector;
#      \q

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4 — Redis (Memorystore)
# (Redis already created in this project as of this session — skip if so.)
#
# NOTE: originally this also created a Serverless VPC Access connector so
# Cloud Run could reach Redis's private IP. That connector resource kept
# failing with an internal GCP error (code 13) across multiple names/IP
# ranges — a genuine platform-side issue, not a config mistake. Switched to
# Cloud Run's newer **Direct VPC egress** instead (`--network`/`--subnet`/
# `--vpc-egress` flags in Phase 9/10) — it reaches the same VPC without a
# connector resource in the middle, so this failure mode doesn't apply.
# ═══════════════════════════════════════════════════════════════════════════
gcloud redis instances create $REDIS_NAME --size=1 --region=$REGION `
  --tier=basic --project $PROJECT

# Grab the Redis internal IP for use in Phase 8:
$REDIS_HOST = gcloud redis instances describe $REDIS_NAME --region=$REGION `
  --project $PROJECT --format="value(host)"
Write-Host "Redis host: $REDIS_HOST"

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 5 — GCS bucket for file uploads (STORAGE_PROVIDER=gcs)
# ═══════════════════════════════════════════════════════════════════════════
gcloud storage buckets create "gs://$BUCKET" --location=$REGION --project $PROJECT

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 6 — Neo4j AuraDB Free (manual — no gcloud equivalent)
# ═══════════════════════════════════════════════════════════════════════════
# 1. Go to https://console.neo4j.io -> sign up / log in with your own account.
# 2. "Create instance" -> Free tier -> any name/region.
# 3. Aura shows the generated password ONCE — copy it now.
# 4. Copy the connection URI shown (neo4j+s://<id>.databases.neo4j.io).
# Paste both into these two variables before Phase 7/8:
$env:NEO4J_URI_VAL = "neo4j+s://<your-instance-id>.databases.neo4j.io"
$env:NEO4J_PW_VAL  = "<paste-the-aura-generated-password>"

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 7 — Secrets in Secret Manager
# ═══════════════════════════════════════════════════════════════════════════
# App-role Postgres password (init_db() creates this DB role automatically,
# but the role's password must match what you put here):
$env:PG_APP_PW = "<CHOOSE-ANOTHER-STRONG-PASSWORD>"

# App SECRET_KEY (JWT signing) and INTERNAL_TASK_SECRET (Cloud Scheduler auth)
# — generate two random values:
$env:APP_SECRET_KEY      = [System.Guid]::NewGuid().ToString() + [System.Guid]::NewGuid().ToString()
$env:INTERNAL_TASK_SECRET_VAL = [System.Guid]::NewGuid().ToString() + [System.Guid]::NewGuid().ToString()

$env:PG_ADMIN_PW | gcloud secrets create postgres-password --data-file=- --project $PROJECT
$env:PG_APP_PW   | gcloud secrets create postgres-app-password --data-file=- --project $PROJECT
$env:NEO4J_PW_VAL | gcloud secrets create neo4j-password --data-file=- --project $PROJECT
$env:APP_SECRET_KEY | gcloud secrets create secret-key --data-file=- --project $PROJECT
$env:INTERNAL_TASK_SECRET_VAL | gcloud secrets create internal-task-secret --data-file=- --project $PROJECT

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 8 — Grant Vertex AI access to Cloud Run's default service account
# (No GOOGLE_APPLICATION_CREDENTIALS key file needed — Cloud Run's attached
#  identity provides ADC automatically.)
# ═══════════════════════════════════════════════════════════════════════════
$PROJECT_NUMBER = gcloud projects describe $PROJECT --format="value(projectNumber)"
$RUNTIME_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:$RUNTIME_SA" --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:$RUNTIME_SA" --role="roles/storage.objectAdmin"

gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:$RUNTIME_SA" --role="roles/cloudsql.client"

# Needed for Direct VPC egress (Phase 9/10) — lets Cloud Run attach to the
# `default` network/subnet without a Serverless VPC Access connector.
gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:$RUNTIME_SA" --role="roles/compute.networkUser"

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 9 — Deploy the API service
# ═══════════════════════════════════════════════════════════════════════════
$ENV_VARS = "ENVIRONMENT=production,ALLOW_MOCK_MFA=false," + `
  "INSTANCE_CONNECTION_NAME=$SQL_CONN,POSTGRES_DB=$DB_NAME,POSTGRES_APP_USER=app_runtime," + `
  "NEO4J_URI=$env:NEO4J_URI_VAL,NEO4J_USER=neo4j," + `
  "REDIS_URL=redis://$REDIS_HOST`:6379/0,CELERY_BROKER_URL=redis://$REDIS_HOST`:6379/1,CELERY_RESULT_BACKEND=redis://$REDIS_HOST`:6379/2," + `
  "VERTEX_PROJECT_ID=$PROJECT,VERTEX_LOCATION=$REGION," + `
  "STORAGE_PROVIDER=gcs,GCS_BUCKET=$BUCKET"

$SECRETS = "POSTGRES_PASSWORD=postgres-password:latest," + `
  "POSTGRES_APP_PASSWORD=postgres-app-password:latest," + `
  "NEO4J_PASSWORD=neo4j-password:latest," + `
  "SECRET_KEY=secret-key:latest," + `
  "INTERNAL_TASK_SECRET=internal-task-secret:latest"

gcloud run deploy karnataka-crime-api `
  --image=$IMAGE --region=$REGION --port=8000 --memory=1Gi --cpu=1 `
  --add-cloudsql-instances=$SQL_CONN `
  --network=default --subnet=default --vpc-egress=private-ranges-only `
  --set-env-vars=$ENV_VARS --set-secrets=$SECRETS `
  --allow-unauthenticated `
  --project $PROJECT

$API_URL = gcloud run services describe karnataka-crime-api --region=$REGION `
  --project $PROJECT --format="value(status.url)"
Write-Host "API deployed at: $API_URL"

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 10 — Deploy the worker service (Celery worker + health sidecar)
# ═══════════════════════════════════════════════════════════════════════════
gcloud run deploy karnataka-crime-worker `
  --image=$IMAGE --region=$REGION --port=8080 --memory=1Gi --cpu=1 `
  --command='sh' `
  --args='-c,uvicorn app.tasks.worker_health:app --host 0.0.0.0 --port $PORT & celery -A app.tasks.celery_app.celery_app worker --loglevel=info --concurrency=4' `
  --no-cpu-throttling --min-instances=1 --ingress=internal `
  --add-cloudsql-instances=$SQL_CONN `
  --network=default --subnet=default --vpc-egress=private-ranges-only `
  --set-env-vars=$ENV_VARS --set-secrets=$SECRETS `
  --project $PROJECT

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 11 — Cloud Scheduler jobs (replace Celery Beat)
# ═══════════════════════════════════════════════════════════════════════════
gcloud scheduler jobs create http gwr-recompute-weekly `
  --schedule="0 2 * * 1" `
  --uri="$API_URL/api/v1/internal/tasks/recompute-gwr" `
  --http-method=POST `
  --headers="X-Internal-Task-Secret=$env:INTERNAL_TASK_SECRET_VAL" `
  --location=$REGION --project $PROJECT

gcloud scheduler jobs create http early-warning-scan-hourly `
  --schedule="0 * * * *" `
  --uri="$API_URL/api/v1/internal/tasks/scan-early-warnings" `
  --http-method=POST `
  --headers="X-Internal-Task-Secret=$env:INTERNAL_TASK_SECRET_VAL" `
  --location=$REGION --project $PROJECT

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 12 — Seed demo data (one-off, via Cloud SQL Auth Proxy from your machine)
# ═══════════════════════════════════════════════════════════════════════════
# Download the proxy once:
Invoke-WebRequest -Uri "https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.14.0/cloud-sql-proxy.x64.exe" `
  -OutFile "cloud-sql-proxy.exe"

# Start it in a separate PowerShell window/job (keeps running):
Start-Process -FilePath ".\cloud-sql-proxy.exe" -ArgumentList "$SQL_CONN --port 5432"

# In this window, point the seed script at localhost through the proxy:
cd backend
$env:POSTGRES_HOST = "127.0.0.1"
$env:POSTGRES_PORT = "5432"
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = $env:PG_ADMIN_PW
$env:POSTGRES_APP_USER = "app_runtime"
$env:POSTGRES_APP_PASSWORD = $env:PG_APP_PW
$env:POSTGRES_DB = $DB_NAME
# -m, not a file path: these scripts import `app.*`, and running them as a file
# puts backend/scripts on sys.path instead of backend/, so the import fails.
python -m scripts.seed_demo_data

# Financial transactions are a separate seeder (the demo seed leaves that table
# almost empty, so every /financial detector returns nothing without this).
python -m scripts.seed_financial_transactions

# Optional: confirms the detectors find what the seeder planted.
python -m scripts.validate_financial_crime

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 13 — Verify
# ═══════════════════════════════════════════════════════════════════════════
curl "$API_URL/health"
curl "$API_URL/api/v1/docs"
gcloud run services logs read karnataka-crime-api --region=$REGION --project $PROJECT --limit=50
