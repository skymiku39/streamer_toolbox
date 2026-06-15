#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

docker compose -f deploy/docker-compose.gcp.yml down "$@"

LOCK_DIR="${STREAMER_DATA_DIR:-/data}/process-locks"
if [[ -d "${LOCK_DIR}" ]]; then
  rm -f "${LOCK_DIR}"/*.pid 2>/dev/null || true
  echo "Cleared process locks in ${LOCK_DIR}"
fi

echo "Stopped GCP compose stacks."
