#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/vstradingai/current}"
cd "$APP_DIR/backend"
set -a; source .env; set +a
PYTHONPATH=. .venv/bin/python - <<'PY'
from app.config import settings
from app.data_sources.zerodha_client import ZerodhaDataSource
s=ZerodhaDataSource(settings.kite_api_key, settings.kite_access_token)
assert s.is_connected(), 'profile/session validation failed'
spot=s.get_spot(); assert spot and float(spot)>0
candles=s.get_candles('3minute', 5); assert candles is not None and len(candles)>0
chain=s.get_option_chain(); assert chain is not None and len(chain)>0
assert not hasattr(s, 'auto_execute'), 'unsafe auto execution surface detected'
print('ZERODHA READ-ONLY VALIDATION PASS')
PY
