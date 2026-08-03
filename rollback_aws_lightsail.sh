#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/vstradingai}"
BACKUP_ROOT="${BACKUP_ROOT:-/opt/vstradingai-backups}"
APP_USER="${APP_USER:-ubuntu}"

if [[ $EUID -ne 0 ]]; then
  echo "Run with sudo: sudo $0 --list | <backup-directory>" >&2
  exit 1
fi

if [[ "${1:-}" == "--list" ]]; then
  find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' 2>/dev/null | sort -r
  exit 0
fi

BACKUP="${1:-}"
if [[ -z "$BACKUP" ]]; then
  echo "Usage: sudo $0 --list | <backup-directory>" >&2
  exit 2
fi
[[ "$BACKUP" = /* ]] || BACKUP="$BACKUP_ROOT/$BACKUP"
ARCHIVE="$BACKUP/application.tar.gz"
[[ -f "$ARCHIVE" ]] || { echo "Backup archive not found: $ARCHIVE" >&2; exit 3; }
(cd "$BACKUP" && sha256sum -c SHA256SUMS) >/dev/null || { echo "Backup checksum verification failed" >&2; exit 4; }

CURRENT_SAFETY=""
if [[ -x "$APP_DIR/backup_aws_lightsail.sh" ]]; then
  CURRENT_SAFETY="$($APP_DIR/backup_aws_lightsail.sh pre-rollback)"
fi

systemctl stop vstradingai-api 2>/dev/null || true
OLD_DIR="${APP_DIR}.before-rollback.$(date -u +%Y%m%dT%H%M%SZ)"
mv "$APP_DIR" "$OLD_DIR"
if ! tar -xzf "$ARCHIVE" -C "$(dirname "$APP_DIR")"; then
  mv "$OLD_DIR" "$APP_DIR"
  systemctl restart vstradingai-api 2>/dev/null || true
  echo "Restore extraction failed; original application restored" >&2
  exit 5
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
systemctl daemon-reload
systemctl restart vstradingai-api
sleep 2
if ! curl -fsS http://127.0.0.1:8000/healthz >/dev/null; then
  systemctl stop vstradingai-api 2>/dev/null || true
  rm -rf "$APP_DIR"
  mv "$OLD_DIR" "$APP_DIR"
  systemctl restart vstradingai-api 2>/dev/null || true
  echo "Restored version failed health check; original application reinstated" >&2
  exit 6
fi
rm -rf "$OLD_DIR"
printf 'Rollback completed from %s\nSafety backup: %s\n' "$BACKUP" "$CURRENT_SAFETY"
