#!/usr/bin/env bash
set -euo pipefail
APP=/opt/vstradingai
SRC="$(cd "$(dirname "$0")" && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REL="$APP/releases/7.1.0-paper-rc1-$STAMP"

echo "[1/7] Safety checks"
test -f "$APP/shared/backend.env"
grep -q '^LIVE_ORDERS_ENABLED=false' "$APP/shared/backend.env" || { echo 'REFUSING DEPLOY: LIVE_ORDERS_ENABLED must be false'; exit 2; }

echo "[2/7] Back up current release pointer and database"
sudo mkdir -p "$APP/backups"
readlink -f "$APP/current" | sudo tee "$APP/backups/pre-v71-current-$STAMP.txt" >/dev/null || true
DB=$(sudo grep '^SQLITE_DB_PATH=' "$APP/shared/backend.env" | cut -d= -f2- || true)
if [[ -n "${DB:-}" && -f "$DB" ]]; then sudo cp -a "$DB" "$APP/backups/vstradingai-$STAMP.db"; fi

echo "[3/7] Copy release"
sudo mkdir -p "$REL"
sudo rsync -a --delete --exclude='.venv' --exclude='node_modules' --exclude='dist' --exclude='.env' "$SRC/" "$REL/"
sudo chown -R ubuntu:ubuntu "$REL"

echo "[4/7] Backend environment"
cd "$REL/backend"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt

echo "[5/7] Tests"
.venv/bin/python -m pytest -q

echo "[6/7] Frontend"
cd "$REL/frontend"
npm ci --silent
npm run build

echo "[7/7] Activate and restart"
sudo ln -sfn "$REL" "$APP/current"
sudo systemctl restart vstradingai-api
sleep 5
sudo systemctl is-active --quiet vstradingai-api
curl -fsS http://127.0.0.1:8000/healthz >/dev/null

echo "DEPLOYED: $REL"
echo "Live broker orders remain OFF. Run ./test_v71_paper.sh next."
