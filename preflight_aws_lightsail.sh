#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/vstradingai}"
fail(){ echo "PREFLIGHT FAIL: $*" >&2; exit 1; }
pass(){ echo "PREFLIGHT PASS: $*"; }
[[ $EUID -eq 0 ]] || fail "run with sudo"
source /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || fail "Ubuntu is required"
pass "OS $PRETTY_NAME"
FREE_MB=$(df -Pm /opt 2>/dev/null | awk 'NR==2{print $4}' || df -Pm / | awk 'NR==2{print $4}')
(( FREE_MB >= 2048 )) || fail "at least 2 GB free disk required (found ${FREE_MB} MB)"
pass "disk space ${FREE_MB} MB"
MEM_MB=$(awk '/MemTotal/{print int($2/1024)}' /proc/meminfo)
(( MEM_MB >= 900 )) || fail "at least 900 MB RAM required"
pass "memory ${MEM_MB} MB"
command -v curl >/dev/null || fail "curl missing"
command -v systemctl >/dev/null || fail "systemd missing"
timedatectl show -p Timezone --value | grep -qx 'Asia/Kolkata' || echo "PREFLIGHT WARN: server timezone is not Asia/Kolkata; application timezone remains explicit"
if ss -ltn '( sport = :8000 )' | grep -q LISTEN && ! systemctl is-active --quiet vstradingai-api 2>/dev/null; then fail "port 8000 is occupied by another service"; fi
mkdir -p "$APP_ROOT/releases" "$APP_ROOT/shared" && touch "$APP_ROOT/shared/.write_test" && rm "$APP_ROOT/shared/.write_test"
pass "filesystem permissions"
echo "PREFLIGHT COMPLETE"
