#!/usr/bin/env bash
set -euo pipefail

SERVICE=vstradingai-api.service
ENV_FILE=/opt/vstradingai/shared/backend.env
PID=$(systemctl show -p MainPID --value "$SERVICE")

echo "SERVICE=$(systemctl is-active "$SERVICE")"
echo "CURRENT=$(readlink -f /opt/vstradingai/current)"
echo "PROCESS_CWD=$(sudo readlink -f "/proc/$PID/cwd")"
echo "COMMIT_OR_VERSION=$(cat /opt/vstradingai/current/VERSION)"
sudo grep -E '^(LIVE_ORDERS_ENABLED|PAPER_REQUIRE_FULL_PIPELINE|KITE_WEBSOCKET_REQUESTED)=' "$ENV_FILE"

health=$(curl -fsS --max-time 20 http://127.0.0.1:8000/healthz)
printf '%s\n' "$health" | python3 -m json.tool
readiness=$(curl -fsS --max-time 20 http://127.0.0.1:8000/api/paper/readiness)
printf '%s\n' "$readiness" | python3 -m json.tool

HEALTH="$health" READINESS="$readiness" python3 - <<'PY'
import json, os
h = json.loads(os.environ['HEALTH'])
r = json.loads(os.environ['READINESS'])
assert h['version'] == '7.9.0-paper-rc1', h
assert h['execution_mode'] == 'PAPER_ONLY', h
assert h['live_orders_enabled'] is False, h
checks = {x['code']: x for x in r['checks']}
assert checks['PAPER_ONLY']['passed'], checks['PAPER_ONLY']
assert checks['FULL_PIPELINE']['passed'], checks['FULL_PIPELINE']
assert checks['WEBSOCKET_OFF']['passed'], checks['WEBSOCKET_OFF']
print('PASS: V7.9.0 safety and full-pipeline gates verified')
PY
