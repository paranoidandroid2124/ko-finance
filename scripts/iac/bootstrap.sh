#!/usr/bin/env bash

# Bootstrap core GCP services (APIs, service accounts, secrets) for K-Finance.
# Usage:
#   PROJECT=kfinance-dev REGION=asia-northeast3 ./scripts/iac/bootstrap.sh

set -euo pipefail

PROJECT="${PROJECT:-kfinance-dev}"
REGION="${REGION:-asia-northeast3}"
SERVICE_ACCOUNT_NAME="${SERVICE_ACCOUNT_NAME:-kfinance-api}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT_NAME}@${PROJECT}.iam.gserviceaccount.com"

echo ">> Enabling core APIs for ${PROJECT}"
gcloud services enable \
  run.googleapis.com \
  compute.googleapis.com \
  sqladmin.googleapis.com \
  secretmanager.googleapis.com \
  cloudscheduler.googleapis.com \
  artifactregistry.googleapis.com \
  --project "${PROJECT}"

echo ">> Creating service account ${SERVICE_ACCOUNT}"
gcloud iam service-accounts create "${SERVICE_ACCOUNT_NAME}" \
  --display-name "K-Finance API" \
  --project "${PROJECT}" || true

echo ">> Granting Cloud Run + Secret Manager roles"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member "serviceAccount:${SERVICE_ACCOUNT}" \
  --role "roles/run.invoker"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member "serviceAccount:${SERVICE_ACCOUNT}" \
  --role "roles/secretmanager.secretAccessor"
gcloud projects add-iam-policy-binding "${PROJECT}" \
  --member "serviceAccount:${SERVICE_ACCOUNT}" \
  --role "roles/cloudsql.client"

echo ">> Creating placeholder secrets"
for secret in "${SERVICE_ACCOUNT_NAME}-database-url" "${SERVICE_ACCOUNT_NAME}-jwt-secret"; do
  if ! gcloud secrets describe "${secret}" --project "${PROJECT}" >/dev/null 2>&1; then
    gcloud secrets create "${secret}" \
      --replication-policy="automatic" \
      --project "${PROJECT}"
    echo "placeholder" | gcloud secrets versions add "${secret}" --data-file=- --project "${PROJECT}" >/dev/null
  fi
done

echo ">> Bootstrap complete."
