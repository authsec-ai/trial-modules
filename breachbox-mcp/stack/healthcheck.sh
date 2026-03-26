#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/.env"
  set +a
fi

docker compose -f "${SCRIPT_DIR}/docker-compose.yml" ps

check_endpoint() {
  local url="$1"
  if curl -fsS --connect-timeout 5 --retry 6 --retry-delay 5 "${url}" >/dev/null; then
    return 0
  fi
  echo "Warning: endpoint check failed for ${url}"
  return 1
}

if [[ -n "${PUBLIC_HOST:-}" ]]; then
  echo
  echo "Checking public endpoints..."
  status_ok=0
  protected_ok=0

  check_endpoint "https://status.${PUBLIC_HOST}/health" || status_ok=1
  check_endpoint "https://protected.${PUBLIC_HOST}/health" || protected_ok=1

  if [[ "${status_ok}" -eq 0 && "${protected_ok}" -eq 0 ]]; then
    echo "Public endpoints responded successfully."
  else
    echo "Public endpoints are not fully ready yet. Check Caddy logs, firewall rules, and DNS resolution."
  fi
else
  echo "PUBLIC_HOST is not set; skipping public endpoint checks."
fi
