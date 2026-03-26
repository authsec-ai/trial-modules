#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-public}"

if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
  echo "Missing ${SCRIPT_DIR}/.env"
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.env"
set +a

if [[ "${MODE}" == "tunnel" ]]; then
  cat <<EOF
[mcp_servers.breachbox_vanilla]
url = "http://127.0.0.1:9000/mcp"

[mcp_servers.breachbox_protected]
url = "http://127.0.0.1:9001"
EOF
  exit 0
fi

if [[ "${MODE}" == "quick" ]]; then
  BASE_URL="${2:-}"
  if [[ -z "${BASE_URL}" ]]; then
    echo "Usage: $0 quick https://<random>.trycloudflare.com"
    exit 1
  fi
  BASE_URL="${BASE_URL%/}"
  cat <<EOF
[mcp_servers.breachbox_vanilla]
url = "${BASE_URL}/vanilla/mcp"

[mcp_servers.breachbox_protected]
url = "${BASE_URL}/protected/mcp"
EOF
  exit 0
fi

cat <<EOF
[mcp_servers.breachbox_vanilla]
url = "https://vanilla.${PUBLIC_HOST}/mcp"

[mcp_servers.breachbox_protected]
url = "https://protected.${PUBLIC_HOST}/mcp"
EOF
