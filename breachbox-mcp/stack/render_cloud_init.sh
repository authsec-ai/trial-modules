#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="${SCRIPT_DIR}/cloud-init.yaml"
OUTPUT_PATH="${1:-${SCRIPT_DIR}/cloud-init.rendered.yaml}"

if [[ ! -f "${SCRIPT_DIR}/.env" ]]; then
  echo "Missing ${SCRIPT_DIR}/.env"
  echo "Copy .env.example to .env and fill the required values first."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.env"
set +a

BUNDLE_URL="${BUNDLE_URL:-${2:-}}"

if [[ -z "${BUNDLE_URL}" ]]; then
  echo "Set BUNDLE_URL in the environment or pass it as the second argument."
  exit 1
fi

escape_sed() {
  printf '%s' "$1" | sed -e 's/[\\/&]/\\&/g'
}

sed \
  -e "s/__DOCKERHUB_NAMESPACE__/$(escape_sed "${DOCKERHUB_NAMESPACE}")/g" \
  -e "s/__DEMO_TAG__/$(escape_sed "${DEMO_TAG}")/g" \
  -e "s/__SKIP_PULL__/$(escape_sed "${SKIP_PULL:-0}")/g" \
  -e "s/__PUBLIC_HOST__/$(escape_sed "${PUBLIC_HOST}")/g" \
  -e "s/__AUTHSEC_CLIENT_ID__/$(escape_sed "${AUTHSEC_CLIENT_ID}")/g" \
  -e "s/__AUTHSEC_APP_NAME__/$(escape_sed "${AUTHSEC_APP_NAME}")/g" \
  -e "s/__AUTHSEC_AUTH_SERVICE_URL__/$(escape_sed "${AUTHSEC_AUTH_SERVICE_URL}")/g" \
  -e "s/__AUTHSEC_SERVICES_URL__/$(escape_sed "${AUTHSEC_SERVICES_URL}")/g" \
  -e "s/__BREACHBOX_CONTROL_TOKEN__/$(escape_sed "${BREACHBOX_CONTROL_TOKEN}")/g" \
  -e "s/__BREACHBOX_PRIMARY_EXPORT__/$(escape_sed "${BREACHBOX_PRIMARY_EXPORT}")/g" \
  -e "s/__BREACHBOX_PRIMARY_SECRET__/$(escape_sed "${BREACHBOX_PRIMARY_SECRET}")/g" \
  -e "s/__BREACHBOX_STATUS_APP_NAME__/$(escape_sed "${BREACHBOX_STATUS_APP_NAME}")/g" \
  -e "s/__BUNDLE_URL__/$(escape_sed "${BUNDLE_URL}")/g" \
  "${TEMPLATE_PATH}" > "${OUTPUT_PATH}"

echo "Wrote ${OUTPUT_PATH}"
