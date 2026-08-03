#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/vstradingai}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
REPORT_DIR="$APP_DIR/deployment/health"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
REPORT="$REPORT_DIR/health_${STAMP}.json"
mkdir -p "$REPORT_DIR"
python3 - "$BASE_URL" "$REPORT" <<'PY'
import json, sys, urllib.request
base, output = sys.argv[1:]
def get(path):
    with urllib.request.urlopen(base + path, timeout=20) as r:
        return json.load(r)
payload = {
    "health": get("/healthz"),
    "system_health": get("/api/system/health"),
    "metrics": get("/api/system/metrics"),
    "alerts": get("/api/system/alerts?limit=20"),
    "version": get("/api/system/version"),
}
with open(output, "w") as f:
    json.dump(payload, f, indent=2)
PY
sha256sum "$REPORT" > "$REPORT.sha256"
ln -sfn "$(basename "$REPORT")" "$REPORT_DIR/latest.json"
find "$REPORT_DIR" -type f -name 'health_*.json*' -mtime +30 -delete
