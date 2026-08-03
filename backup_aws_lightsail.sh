#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vstradingai}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/vstradingai-backups}"
LABEL="${1:-manual}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
VERSION="unknown"
[[ -f "$APP_DIR/VERSION" ]] && VERSION="$(tr -d '[:space:]' < "$APP_DIR/VERSION")"
DEST="$BACKUP_ROOT/${STAMP}_v${VERSION}_${LABEL//[^a-zA-Z0-9._-]/_}"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo $0 [label]" >&2
  exit 1
fi

mkdir -p "$DEST"
chmod 700 "$BACKUP_ROOT" "$DEST"

if [[ -d "$APP_DIR" ]]; then
  tar --exclude='.venv' --exclude='__pycache__' --exclude='.pytest_cache' \
      --exclude='frontend/node_modules' --exclude='frontend/dist' \
      -C "$(dirname "$APP_DIR")" -czf "$DEST/application.tar.gz" "$(basename "$APP_DIR")"
fi

cat > "$DEST/manifest.txt" <<MANIFEST
created_utc=$STAMP
source_dir=$APP_DIR
version=$VERSION
hostname=$(hostname)
label=$LABEL
MANIFEST
sha256sum "$DEST/application.tar.gz" > "$DEST/SHA256SUMS" 2>/dev/null || true
printf '%s\n' "$DEST"
