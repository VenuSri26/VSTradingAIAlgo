#!/usr/bin/env bash
set -euo pipefail
BASE=${BASE_URL:-http://127.0.0.1:8000}
pretty(){ python3 -m json.tool; }

echo '=== HEALTH ==='; curl -fsS "$BASE/healthz" | pretty
echo '=== LIVE DECISION ==='; curl -fsS "$BASE/api/decision/live" | pretty
echo '=== INDICATORS ==='; curl -fsS "$BASE/api/live-market/indicators" | pretty
echo '=== KITE RUNTIME ==='; curl -fsS "$BASE/api/kite-runtime/status" | pretty
echo '=== PAPER MONITOR ==='; curl -fsS "$BASE/api/paper/monitor/status" | pretty
echo '=== PAPER PORTFOLIO ==='; curl -fsS "$BASE/api/paper/portfolio" | pretty
echo '=== PAPER DAILY SUMMARY ==='; curl -fsS "$BASE/api/paper/daily-summary" | pretty
echo '=== PAPER JOURNAL ==='; curl -fsS "$BASE/api/paper/journal?limit=5" | pretty
echo '=== CSV HEADER ==='; curl -fsS "$BASE/api/paper/journal.csv?limit=5" | head -n 2

echo '=== SAFETY ==='
MODE=$(curl -fsS "$BASE/api/paper/daily-summary" | python3 -c 'import sys,json; print(json.load(sys.stdin)["execution_mode"])')
[[ "$MODE" == PAPER_ONLY ]]
echo 'PASS: PAPER_ONLY; no broker order endpoint was invoked.'
