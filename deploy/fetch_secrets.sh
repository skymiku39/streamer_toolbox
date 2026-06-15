#!/usr/bin/env bash
# Fetch .env from GCP Secret Manager for docker compose.
set -euo pipefail

SECRET_NAME="${STREAMER_SECRET_NAME:-streamer-toolbox-env}"
OUTPUT_PATH="${STREAMER_ENV_FILE:-/run/secrets/.env}"
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || true)}"

if [[ -z "${PROJECT_ID}" || "${PROJECT_ID}" == "(unset)" ]]; then
  echo "ERROR: set GCP_PROJECT_ID or run: gcloud config set project <PROJECT_ID>" >&2
  exit 1
fi

mkdir -p "$(dirname "${OUTPUT_PATH}")"
chmod 700 "$(dirname "${OUTPUT_PATH}")"

gcloud secrets versions access latest \
  --secret="${SECRET_NAME}" \
  --project="${PROJECT_ID}" \
  > "${OUTPUT_PATH}"

chmod 600 "${OUTPUT_PATH}"
echo "Wrote ${OUTPUT_PATH} from secret ${SECRET_NAME} (project ${PROJECT_ID})"
