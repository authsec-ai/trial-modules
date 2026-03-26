#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DOCKERHUB_NAMESPACE="${DOCKERHUB_NAMESPACE:-authsec}"
DEMO_TAG="${DEMO_TAG:-breachbox-v1}"
PLATFORM_ARG=()

if [[ -n "${DOCKER_BUILD_PLATFORM:-}" ]]; then
  PLATFORM_ARG=(--platform "${DOCKER_BUILD_PLATFORM}")
fi

build_image() {
  local image_name="$1"
  local dockerfile_path="$2"
  local tag="${DOCKERHUB_NAMESPACE}/${image_name}:${DEMO_TAG}"
  docker build "${PLATFORM_ARG[@]}" -t "${tag}" -f "${ROOT_DIR}/${dockerfile_path}" "${ROOT_DIR}"
}

build_image "breachbox-control-api" "control-api/Dockerfile"
build_image "breachbox-worker" "worker/Dockerfile"
build_image "breachbox-vanilla-mcp" "vanilla/Dockerfile"
build_image "breachbox-protected-mcp" "protected/Dockerfile"
build_image "breachbox-status-ui" "status-ui/Dockerfile"
