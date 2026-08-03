#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/vstradingai}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
PY="$APP_DIR/backend/.venv/bin/python"
REPORT_DIR="$APP_DIR/deployment/validation"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$REPORT_DIR/validation_${STAMP}.txt"

pass(){ printf '%-36s PASS\n' "$1" | tee -a "$REPORT"; }
fail(){ printf '%-36s FAIL: %s\n' "$1" "$2" | tee -a "$REPORT" >&2; exit 1; }

mkdir -p "$REPORT_DIR"
{
  echo "VSTradingAI AWS Validation"
  echo "timestamp_utc=$STAMP"
  echo "host=$(hostname)"
  echo "app_dir=$APP_DIR"
  echo "version=$(tr -d '[:space:]' < "$APP_DIR/VERSION")"
} > "$REPORT"

cd "$APP_DIR/backend"
PYTHONPATH=. "$PY" -m compileall -q app || fail "Python compile" "compileall failed"
pass "Python compile"
PYTHONPATH=. "$APP_DIR/backend/.venv/bin/pytest" -q | tee -a "$REPORT"
pass "Pytest suite"
PYTHONPATH=. "$PY" -m app.config | tee -a "$REPORT"
pass "Configuration validation"
bash -n "$APP_DIR/install_aws_lightsail.sh" "$APP_DIR/test_aws_lightsail.sh" \
  "$APP_DIR/backup_aws_lightsail.sh" "$APP_DIR/rollback_aws_lightsail.sh" \
  "$APP_DIR/daily_health_report.sh" "$APP_DIR/operations_check.sh"
pass "Deployment script syntax"
systemctl is-active --quiet vstradingai-api || fail "Backend service" "service is not active"
pass "Backend service"
curl -fsS "$BASE_URL/healthz" | tee -a "$REPORT" >/dev/null
pass "Health endpoint"
curl -fsS "$BASE_URL/api/system/version" | tee -a "$REPORT" >/dev/null
pass "Version endpoint"
curl -fsS "$BASE_URL/api/system/config-check" | tee -a "$REPORT" >/dev/null
pass "Config API"
curl -fsS "$BASE_URL/api/decision/live" | tee -a "$REPORT" >/dev/null
pass "Decision pipeline API"
curl -fsS "$BASE_URL/api/system/metrics" | tee -a "$REPORT" >/dev/null
pass "Metrics endpoint"
curl -fsS "$BASE_URL/api/system/alerts?limit=5" | tee -a "$REPORT" >/dev/null
pass "Alerts endpoint"
curl -fsS "$BASE_URL/api/institutional-flow/summary" | tee -a "$REPORT" >/dev/null
pass "Institutional flow endpoint"
"$APP_DIR/operations_check.sh" | tee -a "$REPORT"
pass "Operations check"

API_VERSION="$(curl -fsS "$BASE_URL/api/system/version" | "$PY" -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
FILE_VERSION="$(tr -d '[:space:]' < "$APP_DIR/VERSION")"
[[ "$API_VERSION" == "$FILE_VERSION" ]] || fail "Version consistency" "file=$FILE_VERSION api=$API_VERSION"
pass "Version consistency"

MODE="$(set -a; source "$APP_DIR/backend/.env" 2>/dev/null || true; printf '%s' "${TRADING_MODE:-mock}")"
if [[ "$MODE" == "live" ]]; then
  set -a; source "$APP_DIR/backend/.env"; set +a
  PYTHONPATH=. "$PY" - <<'PY' | tee -a "$REPORT"
from app.config import settings
from app.data_sources.zerodha_client import ZerodhaDataSource
source = ZerodhaDataSource(settings.kite_api_key, settings.kite_access_token)
assert source.is_connected(), "Zerodha token validation failed"
print("Zerodha authentication PASS")
PY
  pass "Zerodha authentication"
else
  echo "Zerodha authentication SKIPPED (mock mode)" | tee -a "$REPORT"
fi

sha256sum "$REPORT" > "${REPORT}.sha256"
ln -sfn "$(basename "$REPORT")" "$REPORT_DIR/latest.txt"
echo "AWS Lightsail validation completed successfully."
echo "Report: $REPORT"

# Frontend deployment checks introduced in v1.8.0
test -f "$APP_DIR/frontend/dist/index.html" || { echo "Frontend dist/index.html is missing" >&2; exit 1; }
curl -fsS http://127.0.0.1/ >/dev/null
echo "Frontend dashboard: PASS"
