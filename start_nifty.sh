#!/usr/bin/env bash
# VSTradingAI startup / health validation script.
# Run every trading morning: ./start_nifty.sh
set -uo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/backend" && pwd)"
ENV_FILE="$BACKEND_DIR/.env"
API_PORT="${API_PORT:-8000}"
STATUS=0

pass() { printf "%-22s OK\n" "$1"; }
fail() { printf "%-22s FAILED\n" "$1"; echo "  ERROR: $2"; STATUS=1; }

echo "=== VSTradingAI Startup ==="
echo

# 1. Load canonical environment -------------------------------------------
if [[ ! -f "$ENV_FILE" ]]; then
  fail "ENV FILE" "$ENV_FILE not found. Copy backend/.env.example to backend/.env and fill it in."
  echo
  echo "SYSTEM NOT READY"
  exit 1
fi
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a
pass "ENV FILE"

# 2. Validate required variables via config.py -----------------------------
cd "$BACKEND_DIR" || exit 1
if PYTHONPATH=. python3 -m app.config; then
  pass "CONFIG VALIDATION"
else
  fail "CONFIG VALIDATION" "See details above. Fix backend/.env and re-run."
fi

# 3. Validate Zerodha token (only if TRADING_MODE=live) ---------------------
if [[ "${TRADING_MODE:-mock}" == "live" ]]; then
  if PYTHONPATH=. python3 -c "
from app.data_sources.zerodha_client import ZerodhaDataSource
from app.config import settings
ds = ZerodhaDataSource(settings.kite_api_key, settings.kite_access_token)
import sys
sys.exit(0 if ds.is_connected() else 1)
"; then
    pass "ZERODHA TOKEN"
  else
    fail "ZERODHA TOKEN" "Token invalid/expired. Regenerate KITE_ACCESS_TOKEN via your daily login flow."
  fi
else
  pass "ZERODHA TOKEN (mock mode — skipped)"
fi

# 4. Start/restart backend --------------------------------------------------
if [[ $STATUS -eq 0 ]]; then
  echo
  echo "Starting backend on :$API_PORT ..."
  pkill -f "uvicorn app.main:app" 2>/dev/null || true
  nohup env PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port "$API_PORT" \
    > "$BACKEND_DIR/backend.log" 2>&1 &
  sleep 2

  # 5. Verify health endpoint
  if curl -sf "http://localhost:$API_PORT/healthz" > /dev/null; then
    pass "BACKEND"
  else
    fail "BACKEND" "Health endpoint not responding. Check $BACKEND_DIR/backend.log"
  fi

  # 6. Verify live decision endpoint returns data
  if curl -sf "http://localhost:$API_PORT/api/decision/live" > /dev/null; then
    pass "DASHBOARD API"
  else
    fail "DASHBOARD API" "/api/decision/live not responding. Check $BACKEND_DIR/backend.log"
  fi
else
  echo
  echo "Skipping backend start — fix config errors above first."
fi

echo
if [[ $STATUS -eq 0 ]]; then
  echo "SYSTEM READY FOR MARKET"
else
  echo "SYSTEM NOT READY — see FAILED items above."
fi
exit $STATUS
