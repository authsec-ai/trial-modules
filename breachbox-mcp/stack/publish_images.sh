#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-authsec}"
DEMO_TAG="${DEMO_TAG:-breachbox-v1}"

build_and_push() {
  local image_name="$1"
  local dockerfile_path="$2"
  local tag="${DOCKERHUB_NAMESPACE}/${image_name}:${DEMO_TAG}"
  docker build -t "${tag}" -f "${ROOT_DIR}/${dockerfile_path}" "${ROOT_DIR}"
  docker push "${tag}"
}

build_and_push "breachbox-control-api" "control-api/Dockerfile"
build_and_push "breachbox-worker" "worker/Dockerfile"
build_and_push "breachbox-vanilla-mcp" "vanilla/Dockerfile"
build_and_push "breachbox-protected-mcp" "protected/Dockerfile"
build_and_push "breachbox-status-ui" "status-ui/Dockerfile"

