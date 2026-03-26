#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_PATH="${1:-${SCRIPT_DIR}/breachbox-stack.tar.gz}"

tar -czf "${OUTPUT_PATH}" \
  -C "${SCRIPT_DIR}" \
  Caddyfile \
  cloud-init.yaml \
  codex-mcp.example.toml \
  codex-mcp.tunnel.example.toml \
  docker-compose.yml \
  .env.example \
  build_images.sh \
  healthcheck.sh \
  install.sh \
  publish_images.sh \
  render_cloud_init.sh \
  render_codex_config_snippet.sh \
  restart_protected_mcp.sh \
  reset_demo_state.sh \
  seed_demo_state.sh \
  README.md

echo "Wrote ${OUTPUT_PATH}"
