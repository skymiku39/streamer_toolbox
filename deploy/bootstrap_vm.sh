#!/usr/bin/env bash
# One-time GCE VM bootstrap for streamer-toolbox Product C（純文字 AI 問答）.
# Run as root or with sudo on a fresh Debian/Ubuntu VM.
set -euo pipefail

DATA_MOUNT="${STREAMER_DATA_DIR:-/data}"
CONFIG_MOUNT="${STREAMER_CONFIG_DIR:-/config}"
REPO_DIR="${STREAMER_REPO_DIR:-/opt/streamer_toolbox}"

echo "==> Installing Docker (if missing)"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian \
    $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

echo "==> Creating mount points"
mkdir -p "${DATA_MOUNT}" "${CONFIG_MOUNT}" "${DATA_MOUNT}/logs" "${CONFIG_MOUNT}/knowledge"
mkdir -p /run/secrets
chmod 700 /run/secrets

echo "==> Optional: mount persistent disk"
echo "    If you attached a GCP PD, format and mount it before first deploy, e.g.:"
echo "      sudo mkfs.ext4 -F /dev/disk/by-id/google-streamer-data"
echo "      echo '/dev/disk/by-id/google-streamer-data ${DATA_MOUNT} ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab"
echo "      sudo mount -a"

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  echo "==> Clone repo to ${REPO_DIR} (set STREAMER_REPO_URL if needed)"
  REPO_URL="${STREAMER_REPO_URL:-}"
  if [[ -z "${REPO_URL}" ]]; then
    echo "    Set STREAMER_REPO_URL=https://github.com/<you>/streamer_toolbox.git and re-run"
  else
    git clone "${REPO_URL}" "${REPO_DIR}"
  fi
else
  echo "==> Repo already at ${REPO_DIR}"
fi

echo ""
echo "Next steps:"
echo "  1. gcloud auth application-default login   # or attach SA with secretAccessor"
echo "  2. gcloud secrets create streamer-toolbox-env --data-file=deploy/.env.gcp.example"
echo "     (edit secrets with real TWITCH_* / GOOGLE_AI_API_KEY first)"
echo "  3. Copy knowledge: scp config/knowledge/*.md ${USER}@$(hostname -I | awk '{print $1}'):${CONFIG_MOUNT}/knowledge/"
echo "  4. cd ${REPO_DIR} && bash deploy/up.sh"
