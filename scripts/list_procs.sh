#!/usr/bin/env bash
# List streamer_toolbox Python processes grouped by module.
set -euo pipefail

PATTERN='streamer_toolbox|app\.(main|publishers|subscribers)|ingress_|sub_llm|sub_stream|stream_record|twitch_connector|streamlink'
EXCLUDE='pytest|verify_dedup|multiprocessing\.spawn|list_procs|stop_all'

declare -A GROUPS

while IFS= read -r line; do
  pid="${line%% *}"
  cmd="${line#* }"
  key="other"
  if [[ "${cmd}" =~ -m[[:space:]]+app\.main[[:space:]]+run[[:space:]]+(.+) ]]; then
    rest="${BASH_REMATCH[1]}"
    key="app.main run: ${rest:0:70}"
  elif [[ "${cmd}" =~ -m[[:space:]]+([[:alnum:]_\.]+) ]]; then
    key="${BASH_REMATCH[1]}"
  elif [[ "${cmd}" == *streamlink* ]]; then
    key="streamlink (STT audio)"
  fi
  if [[ -n "${GROUPS[$key]:-}" ]]; then
    GROUPS[$key]="${GROUPS[$key]}, ${pid}"
  else
    GROUPS[$key]="${pid}"
  fi
done < <(
  pgrep -af python 2>/dev/null \
    | grep -E "${PATTERN}" \
    | grep -Ev "${EXCLUDE}" \
    || true
)

echo '=== streamer_toolbox Python processes ==='
total=0
for key in $(printf '%s\n' "${!GROUPS[@]}" | sort); do
  pids="${GROUPS[$key]}"
  count=$(echo "${pids}" | tr ',' '\n' | grep -c . || echo 0)
  total=$((total + count))
  printf '%3sx  %s  [PID: %s]\n' "${count}" "${key}" "${pids}"
done
echo "--- Total ${total} ---"

KEY_MODULES=(
  ingress_ttv_read
  ingress_twitch_audio
  ingress_twitch_stream
  sub_llm
  twitch_connector
  stream_record
  sub_stream_record
)

echo ''
echo '=== Key modules (should be 1 each) ==='
for mod in "${KEY_MODULES[@]}"; do
  cnt=0
  for key in "${!GROUPS[@]}"; do
    if [[ "${key}" == *"${mod}"* ]]; then
      pids="${GROUPS[$key]}"
      cnt=$((cnt + $(echo "${pids}" | tr ',' '\n' | grep -c . || echo 0)))
    fi
  done
  if [[ "${cnt}" -gt 0 ]]; then
    flag=""
    if [[ "${cnt}" -gt 1 ]]; then
      flag=" DUPLICATE!"
    fi
    printf '  %s: %s%s\n' "${mod}" "${cnt}" "${flag}"
  fi
done
