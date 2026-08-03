#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/vstradingai}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
systemctl is-active --quiet vstradingai-api
systemctl is-active --quiet nginx
curl -fsS "$BASE_URL/healthz" >/dev/null
curl -fsS "$BASE_URL/api/system/metrics" >/dev/null
curl -fsS "$BASE_URL/api/system/alerts?limit=5" >/dev/null
test -w "$APP_DIR/backend/data" || mkdir -p "$APP_DIR/backend/data"
echo "operations_check=PASS version=$(tr -d '[:space:]' < "$APP_DIR/VERSION")"
