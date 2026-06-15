#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

bash deploy/fetch_secrets.sh

docker compose -f deploy/docker-compose.gcp.yml up -d --build "$@"

echo ""
echo "Stacks starting. Check status:"
echo "  docker compose -f deploy/docker-compose.gcp.yml ps"
echo "  docker compose -f deploy/docker-compose.gcp.yml logs -f ingress-stack llm-stack"
