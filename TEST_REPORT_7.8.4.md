# Test report — 7.8.4-audit-rc1

Environment: Linux, CPython 3.12, Node/npm from the audit runner. No real broker credential was used.

| Command | Exact result |
|---|---|
| `PYTHONPATH=backend .audit-venv/bin/pytest -q backend/tests` (baseline) | 268 passed, 1 warning |
| `PYTHONPATH=backend .audit-venv/bin/pytest -q backend/tests` (post-change, before final calendar tests) | 271 passed, 1 warning in 3.12s |
| `PYTHONPATH=backend .audit-venv/bin/pytest -q backend/tests/test_paper_auto_trader_v78.py backend/tests/test_v78_paper_loop_certification.py` | 9 passed in 0.34s |
| `npm ci && npm run build` in `frontend` | success; 55 modules; JS 283.75 kB; CSS 11.44 kB |
| `npm audit --omit=dev` | 0 vulnerabilities |
| `.audit-venv/bin/pip check` | no broken requirements |
| `.audit-venv/bin/pip-audit` | failed gate: 3 records in `autobahn 19.11.2` (`PYSEC-2020-25` duplicated by advisory aliases and `CVE-2026-77528`) |
| Uvicorn smoke + `GET /healthz` | HTTP success; `PAPER_ONLY`, `live_orders_enabled=false`, version `7.8.4-audit-rc1` |

Final complete suite: **273 passed, 1 warning in 2.63s**. Targeted deterministic lifecycle/reconciliation/fail-closed run: **6 passed in 0.93s**. Python and shell syntax checks passed. A Starlette deprecation warning remains: FastAPI's compatibility module requests migration from `httpx` to `httpx2`; it does not fail tests.

Deterministic E2E coverage includes candidate approval and rejection, paper entry, target/stop/trailing monitoring, exit, journal, analytics evidence, duplicate suppression, restart reconciliation, finalized candles, stale data, auth errors, risk limits and kill switch. External boundaries are mocked; core decision/risk/ledger logic is not mocked.

Not tested: a real Zerodha login/token, live ticks, actual fills, AWS systemd behavior, full-day UI/operator acceptance, exchange holiday download or real broker error rates.
