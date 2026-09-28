#!/usr/bin/env bash
set -euo pipefail

APP_ROOT=/opt/vstradingai
SHARED_ENV="$APP_ROOT/shared/backend.env"
SERVICE=vstradingai-api.service
SOURCE_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RELEASE_NAME="v7.9.0-paper-rc1-$(date -u +%Y%m%dT%H%M%SZ)"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_NAME"
OLD_RELEASE=$(readlink -f "$APP_ROOT/current" 2>/dev/null || true)
SWITCHED=false

rollback() {
  status=$?
  if [[ $status -ne 0 && "$SWITCHED" == true && -n "$OLD_RELEASE" && -d "$OLD_RELEASE" ]]; then
    echo "Deployment failed; rolling current symlink back to $OLD_RELEASE"
    sudo ln -sfn "$OLD_RELEASE" "$APP_ROOT/current.rollback"
    sudo mv -Tf "$APP_ROOT/current.rollback" "$APP_ROOT/current"
    sudo systemctl restart "$SERVICE" || true
  fi
  exit "$status"
}
trap rollback EXIT

if [[ ! -f "$SHARED_ENV" ]]; then
  echo "STOP: $SHARED_ENV is missing. Create it from backend/.env.example with real Zerodha values."
  exit 1
fi

required_exact() {
  local key=$1 expected=$2
  if ! sudo grep -qx "${key}=${expected}" "$SHARED_ENV"; then
    echo "STOP: $SHARED_ENV must contain ${key}=${expected}"
    exit 1
  fi
}

required_exact LIVE_ORDERS_ENABLED false
required_exact PAPER_REQUIRE_FULL_PIPELINE true
required_exact KITE_WEBSOCKET_REQUESTED false

echo "Source: $SOURCE_DIR"
echo "Target: $RELEASE_DIR"
sudo install -d -o ubuntu -g ubuntu "$APP_ROOT/releases" "$APP_ROOT/backups"
sudo install -d -o ubuntu -g ubuntu "$RELEASE_DIR"
rsync -a --delete \
  --exclude '.git/' --exclude '.audit-venv/' --exclude 'frontend/node_modules/' \
  --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude 'data/*.db' \
  --exclude 'data/*.jsonl' --exclude '.env' \
  "$SOURCE_DIR/" "$RELEASE_DIR/"

for relative_db in data/vstradingai.db backend/data/vstradingai.db; do
  old_db="$APP_ROOT/current/$relative_db"
  if [[ -f "$old_db" ]]; then
    backup_db="$APP_ROOT/backups/$(echo "$relative_db" | tr '/' '-').$(date -u +%Y%m%dT%H%M%SZ)"
    sudo cp -a "$old_db" "$backup_db"
    install -d "$(dirname "$RELEASE_DIR/$relative_db")"
    cp -a "$old_db" "$RELEASE_DIR/$relative_db"
  fi
done
sudo cp -a "$SHARED_ENV" "$APP_ROOT/backups/backend.env.$(date -u +%Y%m%dT%H%M%SZ)"

cd "$RELEASE_DIR/backend"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.lock
PYTHONPATH=. .venv/bin/python -m pytest -q tests

cd "$RELEASE_DIR/frontend"
npm ci
npm run build

sudo ln -sfn "$RELEASE_DIR" "$APP_ROOT/current.next"
sudo mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"
SWITCHED=true
sudo systemctl restart "$SERVICE"

for attempt in {1..30}; do
  if curl -fsS --max-time 5 http://127.0.0.1:8000/healthz > /tmp/vstradingai-v790-health.json; then
    break
  fi
  sleep 1
done

sudo systemctl is-active --quiet "$SERVICE"
python3 - <<'PY'
import json
from pathlib import Path
p = Path('/tmp/vstradingai-v790-health.json')
if not p.exists():
    raise SystemExit('STOP: health endpoint did not respond')
health = json.loads(p.read_text())
assert health.get('version') == '7.9.0-paper-rc1', health
assert health.get('execution_mode') == 'PAPER_ONLY', health
assert health.get('live_orders_enabled') is False, health
print(json.dumps(health, indent=2))
PY

curl -fsS --max-time 10 http://127.0.0.1:8000/api/paper/readiness | python3 -m json.tool
echo "PASS: V7.9.0 installed in PAPER_ONLY mode at $RELEASE_DIR"
echo "Previous release: ${OLD_RELEASE:-none}"
trap - EXIT
