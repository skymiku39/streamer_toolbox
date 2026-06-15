#!/usr/bin/env bash
# Stop streamer_toolbox Python processes (excluding pytest).
set -euo pipefail

PATTERN='streamer_toolbox|app\.(main|publishers|subscribers)|ingress_|sub_llm|sub_stream|stream_record|twitch_connector|streamlink'
EXCLUDE='pytest|verify_dedup|multiprocessing\.spawn|list_procs|stop_all'

mapfile -t PIDS < <(
  pgrep -af python 2>/dev/null \
    | grep -E "${PATTERN}" \
    | grep -Ev "${EXCLUDE}" \
    | awk '{print $1}' \
    || true
)

if [[ ${#PIDS[@]} -eq 0 ]]; then
  echo 'No streamer_toolbox processes found.'
else
  echo "Stopping ${#PIDS[@]} processes..."
  for pid in "${PIDS[@]}"; do
    label="$(ps -p "${pid}" -o args= 2>/dev/null || echo python)"
    echo "  Stop PID ${pid}  ${label}"
    kill "${pid}" 2>/dev/null || true
  done
  sleep 2
  remaining=0
  while read -r pid; do
    ((remaining++)) || true
  done < <(
    pgrep -af python 2>/dev/null \
      | grep -E "${PATTERN}" \
      | grep -Ev "${EXCLUDE}" \
      | awk '{print $1}' \
      || true
  )
  echo "Remaining: ${remaining}"
fi

LOCK_DIR="$(pwd)/data/process-locks"
if [[ -d "${LOCK_DIR}" ]]; then
  rm -f "${LOCK_DIR}"/*.pid 2>/dev/null || true
fi
