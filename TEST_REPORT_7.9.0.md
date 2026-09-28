# V7.9.0 test report

| Command | Result |
|---|---|
| `PYTHONPATH=backend .audit-venv/bin/python -m pytest -q backend/tests` | 278 passed, 1 deprecation warning in 2.64s |
| `npm run build` | Passed; 55 modules; JS 284.35 kB; CSS 11.44 kB |
| Python `py_compile` over backend app/tests | Passed |
| Uvicorn smoke + `GET /healthz` | Passed; version `7.9.0-paper-rc1`, `PAPER_ONLY`, live orders false |
| `GET /api/paper/readiness` with automation deliberately disarmed | Correctly `OFFLINE_BLOCKED`; full-pipeline and WebSocket-off checks passed |
| `npm audit --omit=dev` | 0 vulnerabilities |
| `pip check` | No broken requirements |
| `pip-audit` | Security gate remains failed: 3 advisory records for `autobahn 19.11.2` |

The single warning is FastAPI's compatibility import warning that Starlette's `httpx` test client is deprecated in favour of `httpx2`. It is not a test failure.

The V7.9 tests verify deterministic itemized costs, matching full-pipeline corroboration, direction conflict rejection, health/risk vetoes, and rejection of a current unfinalized pipeline candle. Existing tests continue to cover stale data, authentication failure, kill switch, duplicate suppression, paper entry/monitoring/exit, restart reconciliation, journal and API behavior.

Live Zerodha, AWS systemd, complete market-day soak behavior and real exchange fees were not verifiable in this environment.
