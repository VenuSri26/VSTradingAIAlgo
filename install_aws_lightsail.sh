#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/vstradingai}"
APP_USER="${APP_USER:-ubuntu}"
SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(tr -d '[:space:]' < "$SOURCE_DIR/VERSION")"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BUILD_ID="${BUILD_ID:-$VERSION-$STAMP}"
GIT_COMMIT="${GIT_COMMIT:-unknown}"
APP_ENVIRONMENT="${APP_ENVIRONMENT:-production}"
RELEASE_DIR="$APP_ROOT/releases/${VERSION}-${STAMP}"
CURRENT="$APP_ROOT/current"
PREVIOUS="$(readlink -f "$CURRENT" 2>/dev/null || true)"

[[ $EUID -eq 0 ]] || { echo 'Run with sudo' >&2; exit 1; }
"$SOURCE_DIR/preflight_aws_lightsail.sh"
apt-get update
apt-get install -y python3 python3-venv python3-pip curl unzip nginx nodejs rsync sqlite3 lsof
mkdir -p "$APP_ROOT/releases" "$APP_ROOT/shared/data" "$APP_ROOT/shared/deployment" "$RELEASE_DIR"

if [[ -n "$PREVIOUS" && -x "$PREVIOUS/backup_aws_lightsail.sh" ]]; then
  APP_DIR="$PREVIOUS" "$PREVIOUS/backup_aws_lightsail.sh" pre-deploy
fi

rsync -a --exclude='.git/' --exclude='.env' --exclude='.venv/' --exclude='node_modules/' --exclude='dist/' --exclude='__pycache__/' --exclude='.pytest_cache/' --exclude='*.db' --exclude='*.sqlite3' --exclude='*.jsonl' --exclude='*.log' "$SOURCE_DIR/" "$RELEASE_DIR/"
ln -sfn "$APP_ROOT/shared/data" "$RELEASE_DIR/backend/data"
ln -sfn "$APP_ROOT/shared/deployment" "$RELEASE_DIR/deployment"
if [[ ! -f "$APP_ROOT/shared/backend.env" ]]; then
  cp "$RELEASE_DIR/backend/.env.example" "$APP_ROOT/shared/backend.env"
  chmod 600 "$APP_ROOT/shared/backend.env"
fi
# Keep the shared environment version aligned without changing secrets.
if grep -q '^APP_VERSION=' "$APP_ROOT/shared/backend.env"; then
  sed -i "s/^APP_VERSION=.*/APP_VERSION=$VERSION/" "$APP_ROOT/shared/backend.env"
else
  printf '\nAPP_VERSION=%s\n' "$VERSION" >> "$APP_ROOT/shared/backend.env"
fi
for pair in "BUILD_ID=$BUILD_ID" "BUILD_TIME=$STAMP" "GIT_COMMIT=$GIT_COMMIT" "APP_ENVIRONMENT=$APP_ENVIRONMENT"; do
  key="${pair%%=*}"; value="${pair#*=}"
  if grep -q "^${key}=" "$APP_ROOT/shared/backend.env"; then sed -i "s|^${key}=.*|${key}=${value}|" "$APP_ROOT/shared/backend.env"; else printf '\n%s\n' "$pair" >> "$APP_ROOT/shared/backend.env"; fi
done
ln -sfn "$APP_ROOT/shared/backend.env" "$RELEASE_DIR/backend/.env"
chown -R "$APP_USER:$APP_USER" "$APP_ROOT"

sudo -u "$APP_USER" python3 -m venv "$RELEASE_DIR/backend/.venv"
sudo -u "$APP_USER" "$RELEASE_DIR/backend/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$RELEASE_DIR/backend/.venv/bin/pip" install -r "$RELEASE_DIR/backend/requirements.lock"
sudo -u "$APP_USER" bash -lc "cd '$RELEASE_DIR/frontend' && npm install && npm run build"

cd "$RELEASE_DIR/backend"
sudo -u "$APP_USER" env PYTHONPATH=. .venv/bin/python -m compileall -q app
sudo -u "$APP_USER" env PYTHONPATH=. .venv/bin/pytest -q
sudo -u "$APP_USER" env PYTHONPATH=. .venv/bin/python - <<'PY'
from app import store
with store._conn() as c:
    rows=c.execute('select version from schema_migrations order by version').fetchall()
    assert rows, 'no migrations registered'
print('database migrations PASS')
PY

# Ensure no stale candidate process is occupying port 8001.
STALE_PID="$(lsof -t -iTCP:8001 -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$STALE_PID" ]]; then
  echo "Stopping stale candidate process on port 8001: $STALE_PID"
  kill "$STALE_PID" 2>/dev/null || true
  sleep 2
fi

# Start candidate on a temporary private port before switching production.
sudo -u "$APP_USER" bash -lc "cd '$RELEASE_DIR/backend' && set -a && source .env && set +a && export APP_VERSION='$VERSION' && PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8001 > /tmp/vstradingai-candidate.log 2>&1 & echo \$!" > /tmp/vstradingai-candidate.pid
CANDIDATE_PID=$(cat /tmp/vstradingai-candidate.pid); trap 'kill "$CANDIDATE_PID" 2>/dev/null || true' EXIT
for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:8001/healthz >/dev/null && break; sleep 1; done
curl -fsS http://127.0.0.1:8001/healthz >/dev/null
CANDIDATE_VERSION=$(curl -fsS http://127.0.0.1:8001/api/system/version | "$RELEASE_DIR/backend/.venv/bin/python" -c 'import json,sys;print(json.load(sys.stdin)["version"])')
[[ "$CANDIDATE_VERSION" == "$VERSION" ]] || { echo "candidate version mismatch" >&2; exit 1; }
kill "$CANDIDATE_PID" 2>/dev/null || true; trap - EXIT

ln -sfn "$RELEASE_DIR" "$CURRENT"
cat >/etc/systemd/system/vstradingai-api.service <<SERVICE
[Unit]
Description=VSTradingAI FastAPI Backend
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$CURRENT/backend
Environment=PYTHONPATH=$CURRENT/backend
EnvironmentFile=$APP_ROOT/shared/backend.env
ExecStart=$CURRENT/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
[Install]
WantedBy=multi-user.target
SERVICE
cat >/etc/nginx/sites-available/vstradingai <<NGINX
server {
 listen 80; server_name 13.200.117.219;
 root $CURRENT/frontend/dist; index index.html;
 location /api/ { proxy_pass http://127.0.0.1:8000; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; }
 location /ws/ { proxy_pass http://127.0.0.1:8000; proxy_http_version 1.1; proxy_set_header Upgrade \$http_upgrade; proxy_set_header Connection "upgrade"; }
 location /healthz { proxy_pass http://127.0.0.1:8000; }
 location / { try_files \$uri \$uri/ /index.html; }
}
NGINX
ln -sfn /etc/nginx/sites-available/vstradingai /etc/nginx/sites-enabled/vstradingai
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl daemon-reload
systemctl enable vstradingai-api nginx
systemctl restart vstradingai-api nginx
sleep 3
if ! "$CURRENT/post_deploy_smoke_test.sh"; then
  echo 'Production smoke test failed; rolling back.' >&2
  if [[ -n "$PREVIOUS" && -d "$PREVIOUS" ]]; then ln -sfn "$PREVIOUS" "$CURRENT"; systemctl restart vstradingai-api nginx; fi
  exit 1
fi
mkdir -p "$APP_ROOT/shared/deployment/history"
printf '{"ok":true,"version":"%s","completed_at":"%s","release":"%s"}\n' "$VERSION" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RELEASE_DIR" > "$APP_ROOT/shared/deployment/last_smoke_test.json"
printf '%s version=%s release=%s previous=%s result=success\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$VERSION" "$RELEASE_DIR" "${PREVIOUS:-none}" >> "$APP_ROOT/shared/deployment/history/deployments.log"
echo "Deployment complete: $VERSION"
echo "Edit configuration at $APP_ROOT/shared/backend.env"
