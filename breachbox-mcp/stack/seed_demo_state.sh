#!/usr/bin/env bash
set -euo pipefail

DATA_ROOT="${BREACHBOX_DATA_ROOT:-/srv/breachbox-demo}"
EXPORT_NAME="${BREACHBOX_PRIMARY_EXPORT:-acme-enterprise-export.csv}"
SECRET_NAME="${BREACHBOX_PRIMARY_SECRET:-prod-db-root-token.txt}"

mkdir -p "${DATA_ROOT}/customer-exports" "${DATA_ROOT}/fake-secrets" "${DATA_ROOT}/audit" "${DATA_ROOT}/runtime"

cat > "${DATA_ROOT}/customer-exports/${EXPORT_NAME}" <<'CSV'
customer_id,email,tier,renewal_window,arr_usd
1001,ceo@northstar.example,enterprise,2026-Q2,240000
1002,finance@wildforge.example,business,2026-Q3,72000
1003,secops@daybreak.example,enterprise,2026-Q2,145000
CSV

cat > "${DATA_ROOT}/fake-secrets/${SECRET_NAME}" <<'SECRET'
prod-db://breachbox-demo-root:DemoOnly-NotReal-AuthSec-2026
SECRET

cat > "${DATA_ROOT}/runtime/worker-enabled" <<'FLAG'
1
FLAG

rm -f "${DATA_ROOT}/runtime/worker-heartbeat.json"
rm -f "${DATA_ROOT}/audit/events.jsonl"

echo "Seeded BreachBox demo state under ${DATA_ROOT}"

