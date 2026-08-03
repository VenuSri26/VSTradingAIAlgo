#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
FRONTEND_VERSION=$(python3 -c "import json;print(json.load(open('$ROOT/frontend/package.json'))['version'])")
[[ "$VERSION" == "$FRONTEND_VERSION" ]] || { echo "Version mismatch root=$VERSION frontend=$FRONTEND_VERSION" >&2; exit 1; }
OUT="${1:-$ROOT/../vstradingai_v${VERSION}_deployment_assurance.zip}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/vstradingai_work"
rsync -a --exclude='.git/' --exclude='.env' --exclude='.venv/' --exclude='node_modules/' --exclude='dist/' --exclude='__pycache__/' --exclude='.pytest_cache/' --exclude='*.db' --exclude='*.sqlite3' --exclude='*.jsonl' --exclude='*.log' --exclude='deployment/validation/*' "$ROOT/" "$TMP/vstradingai_work/"
(cd "$TMP" && zip -qr "$OUT" vstradingai_work)
sha256sum "$OUT" > "$OUT.sha256"
echo "$OUT"
