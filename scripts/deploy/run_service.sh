#!/usr/bin/env bash

# Deploy the FastAPI service to Cloud Run using gcloud.
# Usage:
#   PROJECT=kfinance-prod REGION=asia-northeast3 ./scripts/deploy/run_service.sh api

set -euo pipefail

SERVICE="${1:-kfinance-api}"
PROJECT="${PROJECT:-kfinance-dev}"
REGION="${REGION:-asia-northeast3}"
REPO="${REPO:-kfinance}"
IMAGE="asia-northeast3-docker.pkg.dev/${PROJECT}/${REPO}/${SERVICE}:$(git rev-parse --short HEAD)"
SQL_CONNECTION="${SQL_CONNECTION:-${PROJECT}:asia-northeast3:kfinance-sql}"
SERVICE_ACCOUNT="${SERVICE_ACCOUNT:-kfinance-api@${PROJECT}.iam.gserviceaccount.com}"
VPC_CONNECTOR="${VPC_CONNECTOR:-${PROJECT}-connector}"

echo ">> Building container ${IMAGE}"
gcloud config set project "${PROJECT}" >/dev/null
gcloud builds submit --tag "${IMAGE}"

echo ">> Deploying ${SERVICE} to Cloud Run (${REGION})"
gcloud run deploy "${SERVICE}" \
  --image "${IMAGE}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --service-account "${SERVICE_ACCOUNT}" \
  --set-env-vars "PYTHONUNBUFFERED=1" \
  --set-secrets "DATABASE_URL=projects/${PROJECT}/secrets/${SERVICE}-database-url:latest" \
  --set-secrets "AUTH_JWT_SECRET=projects/${PROJECT}/secrets/${SERVICE}-jwt-secret:latest" \
  --vpc-connector "${VPC_CONNECTOR}" \
  --set-cloudsql-instances "${SQL_CONNECTION}" \
  --memory "1Gi" \
  --cpu "1" \
  --max-instances "5" \
  --min-instances "1" \
  --timeout "900s"

echo ">> Deployment finished. Current service URL:"
gcloud run services describe "${SERVICE}" \
  --region "${REGION}" \
  --format "value(status.url)"
