#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "Missing .env in $(pwd)" >&2
  exit 1
fi

set -a
source .env
set +a

: "${NVIDIA_API_KEY:?Missing NVIDIA_API_KEY in .env}"
: "${LITELLM_MASTER_KEY:?Missing LITELLM_MASTER_KEY in .env}"

export NVIDIA_NIM_API_KEY="${NVIDIA_NIM_API_KEY:-$NVIDIA_API_KEY}"

exec litellm --config config.yaml --port "${PORT:-4000}"
