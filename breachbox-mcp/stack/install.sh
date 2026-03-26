#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
  echo "Missing ${SCRIPT_DIR}/.env"
  echo "Copy .env.example to .env and fill the required values first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.env"
set +a

compose() {
  docker compose -f "${SCRIPT_DIR}/docker-compose.yml" "$@"
}

quick_tunnel_url() {
  local container_id=""
  local url=""
  local _i=0
  while [[ ${_i} -lt 30 ]]; do
    container_id="$(compose ps -q cloudflared 2>/dev/null | tail -n 1 || true)"
    if [[ -n "${container_id}" ]]; then
      url="$(docker logs "${container_id}" 2>&1 | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -n 1 || true)"
    fi
    if [[ -n "${url}" ]]; then
      printf '%s\n' "${url}"
      return 0
    fi
    sleep 1
    _i=$((_i + 1))
  done
  return 1
}

if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
fi

if ! docker compose version >/dev/null 2>&1; then
  apt-get update
  apt-get install -y docker-compose-plugin
fi

mkdir -p /opt/breachbox-demo /srv/breachbox-demo
chmod 755 /srv/breachbox-demo

"${SCRIPT_DIR}/seed_demo_state.sh"

if [[ "${SKIP_PULL:-0}" != "1" ]]; then
  compose pull
fi

compose up -d
"${SCRIPT_DIR}/healthcheck.sh"

TUNNEL_URL="$(quick_tunnel_url || true)"

echo
echo "BreachBox stack is up."
echo "Vanilla MCP:   https://vanilla.${PUBLIC_HOST}/mcp"
echo "Protected MCP: https://protected.${PUBLIC_HOST}/mcp"
echo "Status UI:     https://status.${PUBLIC_HOST}/"
if [[ -n "${TUNNEL_URL}" ]]; then
  echo
  echo "Quick Tunnel Base URL: ${TUNNEL_URL}"
  echo "Vanilla MCP (single URL):   ${TUNNEL_URL}/vanilla/mcp"
  echo "Protected MCP (single URL): ${TUNNEL_URL}/protected/mcp"
  echo "Status UI (single URL):     ${TUNNEL_URL}/status/"
fi
