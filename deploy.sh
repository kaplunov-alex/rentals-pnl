#!/usr/bin/env bash
# deploy.sh — Full deployment script for rental-pnl-automation to Google Cloud Run
#
# What this script does (in order):
#   1. Validates prerequisites (gcloud, docker, correct project)
#   2. Enables required GCP APIs
#   3. Creates the Artifact Registry repo (if not exists)
#   4. Pushes secrets to Secret Manager (Anthropic API key + service account JSON)
#   5. Builds and pushes the Docker image via Cloud Build
#   6. Deploys the container to Cloud Run
#   7. Creates/updates the Cloud Scheduler monthly job
#   8. Enables IAP and grants access to allowed users
#
# Usage:
#   ./deploy.sh
#   ./deploy.sh --allowed-users "alice@gmail.com,bob@gmail.com"  # override allowed users
#
# Prerequisites:
#   - gcloud CLI installed and authenticated (`gcloud auth login`)
#   - Docker installed and running (only needed for local builds; Cloud Build doesn't require it)
#   - service_account.json present in project root
#   - .env file present with ANTHROPIC_API_KEY=sk-ant-...
#   - config.yaml updated with your GCP project_id

set -euo pipefail

# ─── Colour helpers ───────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

# ─── Configuration ────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Read from config.yaml (requires python3 + pyyaml, which the project already has)
read_config() {
  python3 -c "
import yaml, sys
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)
print(cfg.get('deployment', {}).get('$1', ''))
"
}

PROJECT_ID="$(read_config project_id)"
REGION="$(read_config region)"
REGION="${REGION:-us-central1}"
SERVICE_NAME="rental-pnl"
REPO_NAME="rental-pnl"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${SERVICE_NAME}"

# Service account used for Cloud Run identity and Scheduler OIDC tokens
DEPLOY_SA="pnl-automation@${PROJECT_ID}.iam.gserviceaccount.com"

# Allowed IAP users — can be overridden via --allowed-users flag
DEFAULT_USERS="$(read_config allowed_users | tr -d "[]'" | tr ',' ' ')"
ALLOWED_USERS="${DEFAULT_USERS}"

# Parse optional CLI flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --allowed-users)
      ALLOWED_USERS="$(echo "$2" | tr ',' ' ')"
      shift 2
      ;;
    *)
      error "Unknown argument: $1"
      ;;
  esac
done

# ─── Step 0: Prerequisites ────────────────────────────────────────────────────
info "Checking prerequisites..."

command -v gcloud >/dev/null 2>&1 || error "gcloud CLI not found. Install from https://cloud.google.com/sdk/docs/install"

# Verify gcloud is authenticated
gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q . \
  || error "Not authenticated. Run: gcloud auth login"

# Validate project_id was set in config.yaml
[[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "YOUR_GCP_PROJECT_ID" ]] \
  && error "Set deployment.project_id in config.yaml before deploying."

# Confirm active project matches config
ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null)"
if [[ "${ACTIVE_PROJECT}" != "${PROJECT_ID}" ]]; then
  warn "Active gcloud project (${ACTIVE_PROJECT}) differs from config (${PROJECT_ID})."
  read -rp "Switch to ${PROJECT_ID}? [y/N] " confirm
  [[ "${confirm}" =~ ^[Yy]$ ]] || error "Aborting. Set the correct project with: gcloud config set project ${PROJECT_ID}"
  gcloud config set project "${PROJECT_ID}"
fi

# Check required local files
[[ -f "${SCRIPT_DIR}/service_account.json" ]] \
  || error "service_account.json not found in project root."
[[ -f "${SCRIPT_DIR}/.env" ]] \
  || error ".env file not found. It must contain ANTHROPIC_API_KEY=sk-ant-..."

ANTHROPIC_API_KEY="$(grep -E '^ANTHROPIC_API_KEY=' "${SCRIPT_DIR}/.env" | cut -d= -f2- | tr -d '"'"'")"
[[ -z "${ANTHROPIC_API_KEY}" ]] && error "ANTHROPIC_API_KEY not found in .env"

info "Prerequisites OK — project: ${PROJECT_ID}, region: ${REGION}"

# ─── Step 1: Enable required APIs ────────────────────────────────────────────
info "Enabling required GCP APIs (this may take a minute on first run)..."
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  iap.googleapis.com \
  --project="${PROJECT_ID}"

# ─── Step 2: Create Artifact Registry repository ─────────────────────────────
info "Ensuring Artifact Registry repository exists..."
if ! gcloud artifacts repositories describe "${REPO_NAME}" \
     --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${REPO_NAME}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Rental P&L automation Docker images" \
    --project="${PROJECT_ID}"
  info "Created Artifact Registry repo: ${REPO_NAME}"
else
  info "Artifact Registry repo already exists."
fi

# ─── Step 3: Push secrets to Secret Manager ──────────────────────────────────
info "Storing secrets in Secret Manager..."

# Helper: create or update a secret
upsert_secret() {
  local secret_name="$1"
  local secret_value="$2"
  if gcloud secrets describe "${secret_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    echo -n "${secret_value}" | gcloud secrets versions add "${secret_name}" \
      --data-file=- --project="${PROJECT_ID}"
    info "Updated secret: ${secret_name}"
  else
    echo -n "${secret_value}" | gcloud secrets create "${secret_name}" \
      --data-file=- --project="${PROJECT_ID}"
    info "Created secret: ${secret_name}"
  fi
}

upsert_secret "anthropic-api-key" "${ANTHROPIC_API_KEY}"

# service_account.json — store the entire JSON file as a secret
if gcloud secrets describe "sheets-service-account" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud secrets versions add "sheets-service-account" \
    --data-file="${SCRIPT_DIR}/service_account.json" --project="${PROJECT_ID}"
  info "Updated secret: sheets-service-account"
else
  gcloud secrets create "sheets-service-account" \
    --data-file="${SCRIPT_DIR}/service_account.json" --project="${PROJECT_ID}"
  info "Created secret: sheets-service-account"
fi

# Grant the Cloud Run service account access to both secrets
info "Granting secret accessor role to service account..."
for secret in anthropic-api-key sheets-service-account; do
  gcloud secrets add-iam-policy-binding "${secret}" \
    --member="serviceAccount:${DEPLOY_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" \
    --quiet
done

# ─── Step 4: Build and push Docker image via Cloud Build ─────────────────────
info "Submitting Cloud Build (builds Docker image and pushes to Artifact Registry)..."
gcloud builds submit "${SCRIPT_DIR}" \
  --config="${SCRIPT_DIR}/clouddeploy/cloudbuild.yaml" \
  --substitutions="_REGION=${REGION},_REPO_NAME=${REPO_NAME}" \
  --project="${PROJECT_ID}"

info "Image pushed: ${IMAGE}:latest"

# ─── Step 5: Deploy to Cloud Run ─────────────────────────────────────────────
info "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image="${IMAGE}:latest" \
  --region="${REGION}" \
  --platform=managed \
  --service-account="${DEPLOY_SA}" \
  --allow-unauthenticated=false \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest" \
  --set-secrets="/secrets/service_account.json=sheets-service-account:latest" \
  --set-env-vars="GOOGLE_APPLICATION_CREDENTIALS=/secrets/service_account.json" \
  --memory=512Mi \
  --cpu=1 \
  --max-instances=1 \
  --min-instances=0 \
  --timeout=300 \
  --project="${PROJECT_ID}"

# Retrieve the deployed service URL for use in later steps
SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --region="${REGION}" --project="${PROJECT_ID}" \
  --format="value(status.url)")"
info "Cloud Run service URL: ${SERVICE_URL}"

# ─── Step 6: Create / update Cloud Scheduler job ─────────────────────────────
info "Setting up Cloud Scheduler monthly job..."
SCHEDULER_JOB="rental-pnl-monthly-run"

if gcloud scheduler jobs describe "${SCHEDULER_JOB}" \
   --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  # Update existing job with new URL (in case service URL changed)
  gcloud scheduler jobs update http "${SCHEDULER_JOB}" \
    --location="${REGION}" \
    --uri="${SERVICE_URL}/api/pipeline/run" \
    --http-method=POST \
    --oidc-service-account-email="${DEPLOY_SA}" \
    --oidc-token-audience="${SERVICE_URL}" \
    --project="${PROJECT_ID}"
  info "Updated Cloud Scheduler job: ${SCHEDULER_JOB}"
else
  gcloud scheduler jobs create http "${SCHEDULER_JOB}" \
    --location="${REGION}" \
    --schedule="0 10 3 * *" \
    --time-zone="America/Los_Angeles" \
    --uri="${SERVICE_URL}/api/pipeline/run" \
    --http-method=POST \
    --message-body="" \
    --oidc-service-account-email="${DEPLOY_SA}" \
    --oidc-token-audience="${SERVICE_URL}" \
    --attempt-deadline="320s" \
    --description="Monthly rental P&L pipeline — runs on the 3rd at 10am PT" \
    --project="${PROJECT_ID}"
  info "Created Cloud Scheduler job: ${SCHEDULER_JOB} (runs 3rd of month, 10am PT)"
fi

# ─── Step 7: Enable IAP and grant user access ─────────────────────────────────
info "Configuring Identity-Aware Proxy (IAP)..."

# IAP on Cloud Run requires the backend service to be linked via a Load Balancer.
# The steps below configure IAP at the Cloud Run level using gcloud beta.
# NOTE: Full IAP on Cloud Run (without a Load Balancer) is a newer feature —
# if the commands below fail, follow the manual setup in the GCP Console:
#   Security → Identity-Aware Proxy → enable for your Cloud Run service.

gcloud beta run services update "${SERVICE_NAME}" \
  --region="${REGION}" \
  --iap \
  --project="${PROJECT_ID}" 2>/dev/null \
  || warn "IAP flag not supported in your gcloud version — enable IAP manually in the GCP Console under Security → Identity-Aware Proxy."

# Grant IAP-secured Web App User role to each allowed user
if [[ -n "${ALLOWED_USERS}" ]]; then
  info "Granting IAP access to allowed users..."
  for email in ${ALLOWED_USERS}; do
    [[ -z "${email}" ]] && continue
    gcloud iap web add-iam-policy-binding \
      --resource-type=cloud-run \
      --service="${SERVICE_NAME}" \
      --region="${REGION}" \
      --member="user:${email}" \
      --role="roles/iap.httpsResourceAccessor" \
      --project="${PROJECT_ID}" \
      && info "  Granted access: ${email}" \
      || warn "  Could not grant IAP access to ${email} — do it manually in GCP Console."
  done
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
info "Deployment complete!"
echo -e "  Service URL : ${GREEN}${SERVICE_URL}${NC}"
echo -e "  Scheduler   : runs 3rd of every month at 10am PT"
echo -e "  IAP users   : ${ALLOWED_USERS:-"(none configured)"}"
echo ""
warn "Next steps if this is your first deploy:"
echo "  1. Enable IAP in GCP Console → Security → Identity-Aware Proxy (if the gcloud beta command above was skipped)"
echo "  2. Verify the service works: curl -H 'Authorization: Bearer \$(gcloud auth print-identity-token)' ${SERVICE_URL}/api/health"
echo "  3. Test the scheduler manually: gcloud scheduler jobs run ${SCHEDULER_JOB} --location=${REGION}"
