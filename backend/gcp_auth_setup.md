# GCP Auth Setup — Karnataka Crime Analytics Platform

Complete command reference to authenticate, configure, and enable all required Google Cloud services for the Vertex AI / Gemini backend.

---

## Prerequisites

- A Google Cloud account with billing enabled
- [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed
- Python 3.11+ and the project `requirements.txt` installed

---

## Step 1 — Install & Initialise the gcloud CLI

```bash
# Verify installation
gcloud --version

# Initialise (browser login + project selection)
gcloud init
```

During `gcloud init` you will:
1. Choose **Log in with a new account** → browser opens
2. Select or create a GCP project
3. Set a default compute region (choose `us-central1` — widest Gemini availability)

---

## Step 2 — Set your active project

```bash
# Replace with your actual project ID
gcloud config set project YOUR_PROJECT_ID

# Confirm it is set correctly
gcloud config get-value project
```

---

## Step 3 — Enable required APIs

Run all at once:

```bash
gcloud services enable \
  aiplatform.googleapis.com \
  speech.googleapis.com \
  storage.googleapis.com \
  secretmanager.googleapis.com \
  cloudresourcemanager.googleapis.com \
  iam.googleapis.com
```

| API | Used for |
|---|---|
| `aiplatform.googleapis.com` | Vertex AI — Gemini LLM + text-embedding-004 |
| `speech.googleapis.com` | Google Cloud Speech-to-Text v2 (Kannada/English) |
| `storage.googleapis.com` | Optional: storing uploaded documents on GCS |
| `secretmanager.googleapis.com` | Optional: storing DB passwords / secrets securely |
| `cloudresourcemanager.googleapis.com` | Project-level IAM checks |
| `iam.googleapis.com` | Service account management |

---

## Step 4 — Create a Service Account (SA)

```bash
# Create the service account
gcloud iam service-accounts create karnataka-crime-backend \
  --display-name="Karnataka Crime Platform Backend" \
  --description="Used by the FastAPI backend + Celery workers"

# Store the full email for use in later commands
export SA_EMAIL="karnataka-crime-backend@$(gcloud config get-value project).iam.gserviceaccount.com"
echo $SA_EMAIL
```

---

## Step 5 — Grant IAM roles to the Service Account

```bash
export PROJECT_ID=$(gcloud config get-value project)

# Vertex AI — LLM inference + embeddings
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user"

# Cloud Speech-to-Text
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/speech.client"

# (Optional) Cloud Storage — if uploading documents to GCS
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectAdmin"

# (Optional) Secret Manager — if storing DB credentials in GCP Secrets
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Step 6A — Local Development: Download SA Key

> **Only needed for local development.** On actual GCP infrastructure (Cloud Run, GKE, Compute Engine), skip to Step 6B.

```bash
# Create keys/ directory inside the backend folder
mkdir -p g:/IBM/backend/keys

# Download the JSON key
gcloud iam service-accounts keys create g:/IBM/backend/keys/sa-key.json \
  --iam-account=$SA_EMAIL

# Point the SDK to the key file
export GOOGLE_APPLICATION_CREDENTIALS="g:/IBM/backend/keys/sa-key.json"

# Add to your shell profile so it persists across sessions
# For PowerShell (Windows):
[System.Environment]::SetEnvironmentVariable("GOOGLE_APPLICATION_CREDENTIALS", "g:\IBM\backend\keys\sa-key.json", "User")

# For bash/zsh (WSL or Mac/Linux):
echo 'export GOOGLE_APPLICATION_CREDENTIALS="$HOME/IBM/backend/keys/sa-key.json"' >> ~/.bashrc
source ~/.bashrc
```

> ⚠️ **IMPORTANT — Never commit the key file.**
> Add it to `.gitignore` immediately:
> ```bash
> echo "backend/keys/" >> g:/IBM/.gitignore
> ```

---

## Step 6B — GCP Infrastructure: Application Default Credentials (ADC)

When the backend runs on **Cloud Run, GKE, or Compute Engine**, no key file is needed. The instance metadata server supplies credentials automatically.

Just make sure the service account is **attached to the resource**:

```bash
# Cloud Run — attach SA at deploy time
gcloud run deploy karnataka-crime-api \
  --service-account=$SA_EMAIL \
  --region=us-central1 \
  ...

# Compute Engine — attach SA to the VM
gcloud compute instances set-service-account INSTANCE_NAME \
  --service-account=$SA_EMAIL \
  --scopes=https://www.googleapis.com/auth/cloud-platform

# GKE — use Workload Identity (recommended over node SA)
# Bind KSA → GSA
gcloud iam service-accounts add-iam-policy-binding $SA_EMAIL \
  --role="roles/iam.workloadIdentityUser" \
  --member="serviceAccount:$PROJECT_ID.svc.id.goog[YOUR_NAMESPACE/YOUR_KSA_NAME]"

kubectl annotate serviceaccount YOUR_KSA_NAME \
  --namespace YOUR_NAMESPACE \
  iam.gke.io/gcp-service-account=$SA_EMAIL
```

---

## Step 7 — Verify ADC works

```bash
# Authenticate as the SA (local testing without a key file)
gcloud auth application-default login

# Or impersonate the SA directly
gcloud auth application-default login \
  --impersonate-service-account=$SA_EMAIL

# Run a quick Vertex AI sanity check
gcloud ai models list --region=us-central1
```

---

## Step 8 — Update `.env` with your project details

Copy `.env.example` → `.env` and fill in:

```bash
cp g:/IBM/backend/.env.example g:/IBM/backend/.env
```

Edit `.env`:

```env
GCP_PROJECT=your-actual-project-id
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=g:/IBM/backend/keys/sa-key.json   # local dev only

LLM_MODEL=gemini-1.5-pro-002
LLM_MODEL_FLASH=gemini-1.5-flash-002
EMBEDDING_MODEL=text-embedding-004
EMBEDDING_DIM=768
```

---

## Step 9 — Test the full stack locally

```bash
# Confirm Vertex AI SDK can authenticate
python - <<'EOF'
import vertexai
from google.auth import default

creds, project = default()
print(f"Authenticated as project: {project}")

vertexai.init(project=project, location="us-central1")
from vertexai.generative_models import GenerativeModel
model = GenerativeModel("gemini-1.5-flash-002")
response = model.generate_content("Say: Vertex AI is working.")
print(response.text)
EOF

# Confirm embeddings
python - <<'EOF'
from langchain_google_vertexai import VertexAIEmbeddings
import os

embedder = VertexAIEmbeddings(
    model_name="text-embedding-004",
    project=os.environ["GCP_PROJECT"],
    location="us-central1",
)
vec = embedder.embed_query("Test embedding for Karnataka crime platform")
print(f"Embedding dim: {len(vec)} (expected 768)")
EOF
```

---

## Step 10 — (Optional) Store DB password in Secret Manager

```bash
# Store the PostgreSQL password as a secret
echo -n "your_postgres_password" | \
  gcloud secrets create karnataka-postgres-password \
    --data-file=- \
    --replication-policy=automatic

# Grant the SA access to read it
gcloud secrets add-iam-policy-binding karnataka-postgres-password \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

# Read it back to verify
gcloud secrets versions access latest \
  --secret=karnataka-postgres-password
```

---

## Quick Reference — IAM Roles Summary

| Role | Service | Why |
|---|---|---|
| `roles/aiplatform.user` | Vertex AI | Gemini inference + text-embedding-004 |
| `roles/speech.client` | Cloud Speech | Kannada/English audio transcription |
| `roles/storage.objectAdmin` | Cloud Storage | Document uploads (optional) |
| `roles/secretmanager.secretAccessor` | Secret Manager | DB credentials at runtime (optional) |

---

## Troubleshooting

### `google.auth.exceptions.DefaultCredentialsError`
```bash
# Ensure the env var is set in the current shell
echo $GOOGLE_APPLICATION_CREDENTIALS

# Re-export it
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/sa-key.json"

# Or re-run ADC login
gcloud auth application-default login
```

### `PERMISSION_DENIED` on Vertex AI
```bash
# Check the SA has aiplatform.user
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:$SA_EMAIL" \
  --format="table(bindings.role)"
```

### `API not enabled` error
```bash
# Re-run the enable block from Step 3
gcloud services enable aiplatform.googleapis.com speech.googleapis.com
```

### Model quota / region not available
```bash
# List available Gemini models in your region
gcloud ai models list --region=us-central1 --filter="displayName~gemini"

# Switch to asia-south1 (Mumbai) for lower latency from India
gcloud config set compute/region asia-south1
# Then update GCP_LOCATION=asia-south1 in .env
```

> **Note on region for India deployment:** `us-central1` has the widest Gemini model availability. `asia-south1` (Mumbai) may offer lower latency but check Gemini availability there before switching — not all versions are available in all regions.
