#!/usr/bin/env bash
set -euo pipefail

DISK=/dev/disk/by-id/google-streamer-data
if ! blkid "${DISK}" >/dev/null 2>&1; then
  mkfs.ext4 -F "${DISK}"
fi
if ! grep -q google-streamer-data /etc/fstab; then
  echo "${DISK} /data ext4 defaults,nofail 0 2" >> /etc/fstab
fi
mkdir -p /data /config/knowledge /run/secrets /data/logs
mount -a
chmod 700 /run/secrets

if ! command -v docker >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq ca-certificates curl gnupg git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "${VERSION_CODENAME}") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi

if [[ ! -d /opt/streamer_toolbox/.git ]]; then
  git clone https://github.com/skymiku39/streamer_toolbox.git /opt/streamer_toolbox
fi

if compgen -G "/opt/streamer_toolbox/config/knowledge/*.md" >/dev/null; then
  cp /opt/streamer_toolbox/config/knowledge/*.md /config/knowledge/
fi

cd /opt/streamer_toolbox
export GCP_PROJECT_ID=yt-livechat-bot-490312
bash deploy/fetch_secrets.sh
docker compose -f deploy/docker-compose.gcp.yml up -d --build

echo "=== Setup complete ==="
docker compose -f deploy/docker-compose.gcp.yml ps
