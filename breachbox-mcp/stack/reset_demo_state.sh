#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"${SCRIPT_DIR}/seed_demo_state.sh"
docker compose -f "${SCRIPT_DIR}/docker-compose.yml" up -d breachbox-control-api breachbox-worker breachbox-status-ui breachbox-vanilla-mcp breachbox-protected-mcp caddy
docker compose -f "${SCRIPT_DIR}/docker-compose.yml" restart breachbox-worker

echo "BreachBox demo state reset complete."

