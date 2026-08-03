# VSTradingAI — Nifty50 AI Trading Dashboard

Everything — backend, frontend, tests, deployment guide — ships in **one
zip**. There is no separate/second file; `vstradingai.zip` is the complete,
current deliverable each time it's regenerated.

For AWS Lightsail deployment (transfer → install → run → test), see
**[DEPLOYMENT.md](./DEPLOYMENT.md)**.

## Quick start

```bash
cd backend
cp .env.example .env          # TRADING_MODE=mock works with zero setup
pip install -r requirements.txt --break-system-packages
PYTHONPATH=. python -m app.config        # validate config
PYTHONPATH=. uvicorn app.main:app --reload --port 8000
# in another terminal:
curl http://localhost:8000/api/decision/live | python -m json.tool
```

Or from the project root: `./start_nifty.sh` (does env load → config
validation → Zerodha token check if live → backend start → health checks).

Frontend:
```bash
cd frontend
npm install
npm run dev       # expects backend on http://localhost:8000, override with VITE_API_BASE_URL
```

**Run tests:**
```bash
cd backend
pip install pytest --break-system-packages
pytest -v
```
Or, without installing pytest, run the plain-Python scripts directly
(same assertions, zero extra dependencies — this is how they were verified
during development):
```bash
python3 tests/verify_offline.py            # 15 checks — core pipeline
python3 tests/test_store.py                # 17 checks — SQLite session/position store
python3 tests/test_position_info.py        #  5 checks — mark-to-market P&L
python3 tests/test_backtest.py             # 13 checks — backtest evaluator
python3 tests/test_greeks.py               # 21 checks — Black-Scholes Greeks/IV
python3 tests/test_greeks_e2e.py           # pipeline-level Greeks integration
python3 tests/test_candlestick_patterns.py #  8 checks — pattern detection
python3 tests/test_historical_data.py      #  5 checks — nsepython fallback contract
python3 tests/test_order_placement_logic.py #  4 checks — order placement branching
```

## Going live with real Zerodha data

1. `pip install kiteconnect --break-system-packages`
2. In `backend/.env`: set `TRADING_MODE=live`, `KITE_API_KEY`, `KITE_API_SECRET`,
   generate a fresh `KITE_ACCESS_TOKEN` via your daily Kite login flow.
3. Run `./start_nifty.sh` — it will refuse to start in live mode if the
   token is invalid or any required var is missing (see `app/config.py`).
4. `NIFTY_INSTRUMENT_TOKEN`/`INDIA_VIX_TOKEN` in `zerodha_client.py` are
   standard NSE tokens — verify against your own Kite instrument dump before
   trusting them in production.

## IMPLEMENTATION STATUS

### Completed
- Full decision pipeline (spec section 37): market data → features → 9
  agents (HTF Bias, Regime, Trend, Momentum, Liquidity, Options/OI, Gamma,
  Trap Detection, Risk) → weighted alignment → A+/A/B/C/NO_TRADE grading →
  CE BUY / PE BUY / NO TRADE.
- Market Structure detection (BOS/CHOCH, swing HH/HL/LH/LL sequencing, Fair
  Value Gaps, simplified order blocks) computed for real from OHLC.
- Institutional Narrative generator — deterministic template sourced only
  from real computed values (never an LLM call, so it can't say anything
  the data doesn't support).
- All indicator math (EMA, RSI, MACD, ADX, ATR, VWAP) computed for real from
  OHLC — no hard-coded/fabricated scores anywhere; unavailable data returns
  `NOT_AVAILABLE`, never a guess.
- Risk Agent veto authority: max trades/day, daily loss limit, consecutive
  losses, stale data, VIX spike, minimum RR, proximity to close.
- Trade plan builder prices entry/SL/T1/T2 off real option-chain LTPs, never
  invented prices.
- Entry checklist, NO-TRADE explainability, bull/bear/watch flags — all
  derived from actual agent output.
- Source-tagging (`ZERODHA` / `MOCK` / `CALCULATED` / etc.) on every field
  per spec section 27; `MockDataSource` is structurally prevented from
  running when `TRADING_MODE=live`.
- Canonical single `.env` + startup validation script addressing the
  multi-.env / stale-token failure mode described in the brief (section 28).
- Consolidated REST API matching spec section 30
  (`/api/decision/live`, `/api/market/snapshot`, `/api/agents/status`,
  `/api/options/snapshot`, `/api/positions/current`, `/api/analytics/session`,
  `/api/system/health`).
- Audit logging to JSONL for every decision (section 39, self-learning prep).
- **Full dashboard** matching spec section 34's layout: header, 4 metric
  cards, AI decision card, alignment score, risk status, all 9 agent bars,
  levels grid, technical indicators, market structure (BOS/CHOCH/FVG/order
  blocks), option chain table (ATM±5, call/put wall highlighting), liquidity
  map, gamma analysis, trap detection, bull/bear/watch flags, agent
  explainability panel, institutional narrative, entry checklist, current
  position, session analytics, and system health — all reading live data
  from the backend, dark theme per spec section 33 palette, zero mock values
  in the UI layer.
- **Persisted state (SQLite)**: session counters (trades/wins/losses/PnL/
  consecutive losses) and positions now survive a backend restart —
  `app/store.py`. Manual position open/close endpoints
  (`POST /api/positions/open`, `POST /api/positions/close`) since there's no
  live broker order flow wired up yet; you record the trade here after
  actually placing it in Kite.
- **Real-time WebSocket push** (`/ws/decision`) replacing polling, per spec
  section 32. Frontend hook (`useLiveDecision.ts`) connects via WebSocket
  first and automatically falls back to 3s polling if the socket can't
  connect or drops — dashboard shows a LIVE/POLLING indicator in the header.
- **Backtest/self-learning scaffold** (`app/backtest.py`, spec sections
  40-41): walks any forward price series against a logged trade plan and
  computes HIT_T1/HIT_T2/HIT_SL, MFE, MAE, and realized RR. Deliberately
  does not auto-adjust the strategy — a human reviews `GET
  /api/analytics/backtest` output. Verified against synthetic price paths
  (13/13 tests pass); wiring it to real historical Zerodha data is a
  one-function job once you're live (see the docstring in that file).
- Session Analytics now derives skip/block counts from deduplicated audit
  log entries (not from every 3s poll — that would have wildly overcounted).
- **Real Black-Scholes Greeks** (`app/greeks.py`): delta/gamma/theta/vega/IV
  for every leg in the option chain, solved from each leg's own market LTP
  (not assumed). Optional `py_vollib_vectorized` fast-path, scipy-based
  fallback always available. Verified against textbook BS properties
  (put-call parity, gamma symmetry, delta limits) — 21/21 tests. Two real
  bugs were found and fixed in the process: the IV solver's floor used
  undiscounted intrinsic value (rejected valid short-dated ITM prices), and
  the mock chain's ITM pricing used only 35% of true intrinsic value (could
  price below its own floor). Both fixed with regression tests.
- **Real net GEX** on the Gamma Agent — actual gamma × OI per strike, not
  just OI-wall inference. Trade plans now show real delta/theta/IV.
- **Candlestick pattern detection** (doji, hammer, shooting star,
  bullish/bearish engulfing) in `market_structure.py` — pure pandas/numpy,
  no TA-Lib dependency required. 8/8 tests pass.
- **`app/historical_data.py`** — optional `nsepython` integration to feed
  real Nifty history into the backtest evaluator (previously only tested
  against synthetic data). Untested against a live nsepython install (no
  network here) — the fallback/error-handling contract is tested (5/5), the
  actual NSE API call is not.
- **Zerodha order placement** (`zerodha_client.py`): `place_order` and
  `place_autoslice_order` (auto-splits orders exceeding exchange freeze
  limits, per pykiteconnect's newer SDK method). Not called automatically
  anywhere — positions are still opened/closed manually via `app/store.py`
  by design (human stays in the loop before real capital moves). Branching
  logic tested with a fake Kite client (4/4); the real Kite API call is
  untested (no network/credentials here).

### Reused
- N/A — no existing repository was provided to audit or reuse from. This is
  a from-scratch build per your follow-up instruction.

### New files
```
backend/app/models.py, features.py, config.py, pipeline.py, routes.py,
  schemas.py, main.py, audit_log.py, store.py, analytics.py, backtest.py,
  greeks.py, historical_data.py
backend/app/agents/{base,technical_agents,htf_bias,liquidity,
  options_agents,risk,alignment,market_structure,narrative}.py
backend/app/data_sources/{base,mock_source,zerodha_client}.py
backend/tests/{test_pipeline,test_store,test_position_info,test_backtest,
  test_greeks,test_greeks_e2e,test_candlestick_patterns,
  test_historical_data,test_order_placement_logic,verify_offline}.py
backend/requirements.txt, .env.example
start_nifty.sh
DEPLOYMENT.md
frontend/src/types/decision.ts, services/api.ts, hooks/useLiveDecision.ts,
  Dashboard.tsx
frontend/src/cards/InfoCards.tsx, OptionAndStructureCards.tsx, PanelCards.tsx
frontend/package.json
```

### Tests
50 logic checks validated by direct execution in this sandbox (no network
here to install pytest — same assertions are also written as proper
`pytest`-compatible scripts in `backend/tests/`; run `pytest -v` on your
machine for the formal report). All 50 passed, across four suites:

- `test_pipeline.py` (15) — pipeline runs cleanly, NO TRADE is the honest
  default on noisy data, only A/A+ grades are ever actionable, trade plans
  price off real chain data with SL < LTP < T1 < T2, Risk Agent vetoes
  correctly and approves when clean, agent weights sum to 1.0, alignment
  returns `None` (not a fake number) when all agents are unavailable,
  config validation catches bad weights/missing live credentials, and a
  simulated broker outage cascades to `NOT_AVAILABLE` + `NO_TRADE` + `RED`
  health without crashing.
- `test_store.py` (17) — SQLite position lifecycle (open/close/PnL math),
  session counters accumulate correctly across multiple trades, consecutive
  losses increment and reset correctly, audit-log-derived skip/block counts
  are accurate and deduplicated.
- `test_position_info.py` (5) — live mark-to-market P&L calculation against
  the option chain is internally consistent.
- `test_backtest.py` (13) — HIT_T1/HIT_T2/HIT_SL classification, MFE/MAE
  computation, realized RR, and per-grade win-rate summarization are all
  correct against synthetic price paths.

### Live-data status
**Not connected** — this environment has no network access and no Zerodha
credentials. `ZerodhaDataSource` is written against the real `kiteconnect`
SDK (correct method calls, token validation, no-lookahead candle trimming)
but has never talked to a live Kite session. Test it on your machine with a
real `KITE_ACCESS_TOKEN` before trusting it.

### Remaining blockers
BLOCKER: No live Zerodha session, and no real nsepython/nework-dependent calls, available in this environment.
WHY: This sandbox has no internet access and you don't yet have a deployment target picked.
USER ACTION: Copy this project to a machine with network access, `pip install -r requirements.txt` (plus any optional deps you want from the commented-out list), supply real Kite credentials in `backend/.env`, run `./start_nifty.sh`.
COMMAND TO CONTINUE: none needed from me — ping me back here with any errors from your real run and I'll fix them.

Specifically untested here for the same reason (no network):
- `ZerodhaDataSource` and its new `place_order`/`place_autoslice_order` —
  the branching/fallback logic is unit-tested (4/4), the actual Kite API
  calls are not.
- `app/historical_data.py`'s `fetch_nifty_history` — the fallback contract
  is tested (5/5), the real nsepython/NSE API call is not.
- `py_vollib_vectorized` fast-path in `app/greeks.py` — the scipy fallback
  it's tested against is mathematically equivalent, but the actual fast-path
  code branch has never executed (package not installed here).

Also not yet built: order execution isn't wired into the decision pipeline
automatically (by design — positions are opened/closed manually via
`app/store.py`'s endpoints, keeping a human in the loop before real capital
moves), and the self-learning layer beyond the backtest scaffold (spec
section 40's MFE/MAE/false-positive tracking is captured in the audit log
but not yet aggregated into a report).

### Commands to run
See "Quick start" above.

### Dashboard URL
`http://localhost:5173` (frontend) once both `npm run dev` and the backend
are running.

## 2026 Safe Architecture Upgrade

This package adds IST-correct market timing, protected and validated position APIs, SQLite WAL and single-open-position protection, Zerodha lot-size metadata support, truthful market timestamp handling, continuous WebSocket snapshots, repaired pytest collection, AWS Lightsail installation/testing scripts, and secret-safe Git defaults.

Automatic Zerodha order execution remains disabled by design. The current release is intended for decision support, mock testing and controlled paper trading until sufficient forward testing is completed.

See `AWS_LIGHTSAIL_GUIDE.md` for installation and validation.

## Version and change verification

Current release: **1.1.0**

- `VERSION` is the canonical release number.
- `CHANGELOG.md` summarizes release changes.
- `CHANGE_REGISTER.md` stores the detailed verification and rollback record.
- `GET /api/system/version` reports runtime version/build metadata.
- Every AWS validation creates a timestamped report under `deployment/validation/`.
- Every AWS installation records an entry in `deployment/history/deployments.log`.

### Backup and rollback

Create a manual server backup:

```bash
sudo /opt/vstradingai/backup_aws_lightsail.sh manual
```

List available restore points:

```bash
sudo /opt/vstradingai/rollback_aws_lightsail.sh --list
```

Restore one backup:

```bash
sudo /opt/vstradingai/rollback_aws_lightsail.sh <backup-directory-name>
```

## Version 1.3.0 additions

This release adds Zerodha session health and a persistent, human-reviewed trade-setup workflow without enabling automatic broker execution.

```bash
curl http://127.0.0.1:8000/api/system/zerodha-health
curl http://127.0.0.1:8000/api/setups
```

Approve a generated setup:

```bash
curl -X POST http://127.0.0.1:8000/api/setups/1/review \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: $ADMIN_TOKEN" \
  -d '{"status":"APPROVED","note":"Approved for paper observation"}'
```

Approval is an audit action only. It does not send an order to Zerodha.

## Paper Execution and Risk Engine (v1.4.0)

Version 1.4.0 extends approved setups into a strictly paper-only lifecycle. It does not send orders to Zerodha.

1. Approve a generated setup using `/api/setups/{id}/review`.
2. Open a risk-sized paper trade using `POST /api/paper/execute`.
3. Monitor or close it using `POST /api/paper/monitor`.
4. Review history using `GET /api/paper/trades`.

Risk sizing uses `PAPER_CAPITAL`, `MAX_RISK_PER_TRADE_PCT`, `NIFTY_LOT_SIZE`, and `PAPER_SLIPPAGE_RUPEES`. Estimated costs are configurable through `PAPER_COST_RATE`; they are an analytical estimate, not an official Zerodha contract note.

## Strategy validation (v1.5.0)
Version 1.7.0 adds a conservative offline replay engine. It enters strictly on the candle after a signal, includes configurable slippage and costs, treats same-candle stop/target conflicts as stop-loss, and supports expanding walk-forward splits. It never changes live configuration.

Run a CSV replay:

```bash
cd backend
source .venv/bin/activate
python scripts_validate_strategy.py candles.csv signals.csv
```

Candle columns: `timestamp,open,high,low,close`.
Signal columns: `signal_time,side,entry,stop_loss,target,regime,grade`.


## Multi-Agent Confidence Controls (v1.6.0)
The decision payload now includes `alignment.coverage_ratio`, `alignment.disagreement_score`, `alignment.calibrated_confidence`, `alignment.family_contributions`, and a top-level `debate` object. Set `MIN_AGENT_COVERAGE` and `MAX_AGENT_DISAGREEMENT` in `.env` to tune conservative qualification gates. Automatic Zerodha execution remains disabled.


## Production monitoring (v1.7.0)

Operational endpoints:

```bash
curl http://127.0.0.1:8000/api/system/metrics
curl http://127.0.0.1:8000/api/system/alerts?limit=20
```

AWS operations:

```bash
sudo /opt/vstradingai/operations_check.sh
sudo /opt/vstradingai/daily_health_report.sh
systemctl list-timers 'vstradingai-*'
```

Daily health reports are retained for 30 days under `/opt/vstradingai/deployment/health`. Daily backups use the existing checksum-protected backup workflow. Monitoring does not place Zerodha orders or modify agent decisions.


## Version 1.8 Dashboard Operations
The dashboard now exposes metrics, alerts, deployment version, Zerodha session status, setup review and paper execution controls. Protected actions require ADMIN_TOKEN. No UI control places a live Zerodha order.


## Automated paper monitoring (v1.9.0)

The backend resumes monitoring any SQLite `OPEN` paper trade after restart. It refreshes the matching option price from the configured data source and automatically performs paper-only SL/T1/T2/EOD exits. It never calls Zerodha order placement.

Endpoints: `/api/paper/monitor/status`, `/api/paper/monitor/events`, and protected `/api/paper/monitor/run-once`.

## Version 2.0 deployment assurance
Run `sudo ./preflight_aws_lightsail.sh` before deployment. The installer stages releases under `/opt/vstradingai/releases`, validates a candidate on port 8001, switches `/opt/vstradingai/current` only after tests pass, and automatically restores the previous release if production smoke tests fail.

Create a clean distributable with `./package_release.sh`. Runtime databases, logs, tokens and generated frontend files are excluded.

## 2.3.0 RC1 Workspaces

- **Operations:** read-only server resources, logs, deployment history, backups and Zerodha health.
- **Agents:** live multi-agent registry, evidence families, votes, debate and supervisor decision.
- **Strategy Lab:** conservative research-only replay using pasted JSON candle/signal data.

No workspace can place a live Zerodha order.
