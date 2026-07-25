#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

LOG_FILE="${LOG_FILE:-litellm-monitor.log}"
PORT="${PORT:-4000}"
SMOKE_INTERVAL="${SMOKE_INTERVAL:-300}"
CHECK_INTERVAL="${CHECK_INTERVAL:-30}"

log() {
  printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" | tee -a "$LOG_FILE"
}

load_env() {
  set -a
  source .env
  set +a
  export NVIDIA_NIM_API_KEY="${NVIDIA_NIM_API_KEY:-$NVIDIA_API_KEY}"
}

is_listening() {
  lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1
}

start_proxy() {
  log "LiteLLM is not listening on port $PORT; starting ./start.sh"
  nohup ./start.sh >> litellm-autostart.log 2>&1 &
}

smoke_model() {
  local model="$1"
  curl -sS --max-time 90 "http://127.0.0.1:${PORT}/v1/chat/completions" \
    -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"model\":\"${model}\",\"messages\":[{\"role\":\"user\",\"content\":\"responda só: ok\"}]}" \
    | grep -q '"content":"ok"'
}

load_env
last_smoke=0
log "monitor started"

while true; do
  if ! is_listening; then
    start_proxy
    sleep "$CHECK_INTERVAL"
    continue
  fi

  now="$(date +%s)"
  if (( now - last_smoke >= SMOKE_INTERVAL )); then
    for model in operario arquiteto revisor; do
      if smoke_model "$model"; then
        log "smoke ok: $model"
      else
        log "smoke failed: $model; keeping monitor alive"
      fi
    done
    last_smoke="$now"
  fi

  sleep "$CHECK_INTERVAL"
done
