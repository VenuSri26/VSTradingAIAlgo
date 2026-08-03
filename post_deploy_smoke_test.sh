#!/usr/bin/env bash
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
WEB_URL="${WEB_URL:-http://127.0.0.1}"
for path in /healthz /api/system/version /api/system/config-check /api/system/zerodha-health /api/system/metrics '/api/system/alerts?limit=5' /api/decision/live /api/setups /api/paper/trades /api/paper/monitor/status /api/paper/portfolio /api/risk/status /api/analytics/paper /api/replay /api/institutional-flow/summary; do
  curl --max-time 15 -fsS "$BASE_URL$path" >/dev/null || { echo "SMOKE FAIL $path" >&2; exit 1; }
  echo "SMOKE PASS $path"
done
curl --max-time 15 -fsS "$WEB_URL/" | grep -qi '<html' || { echo 'SMOKE FAIL frontend' >&2; exit 1; }
echo 'SMOKE PASS frontend'
