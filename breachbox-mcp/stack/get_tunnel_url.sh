#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

container_id=""

for _i in $(seq 1 30); do
  container_id="$(docker compose -f "${SCRIPT_DIR}/docker-compose.yml" ps -q cloudflared 2>/dev/null | tail -n 1 || true)"
  if [[ -n "${container_id}" ]]; then
    URL="$(docker logs "${container_id}" 2>&1 | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -n 1 || true)"
  else
    URL=""
  fi
  if [[ -n "${URL}" ]]; then
    printf '%s\n' "${URL}"
    exit 0
  fi
  sleep 1
done

echo "No Cloudflare quick tunnel URL found in cloudflared logs." >&2
exit 1
