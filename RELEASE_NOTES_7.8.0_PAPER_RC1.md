# VSTradingAI 7.8.0 Paper RC1

## Outcome

v7.8 closes the manual gap between a qualified live-market preview and a
simulated paper position. The new worker is disabled by default and can only
write to the paper ledger. It contains no broker order placement path.

## Added

- Autonomous paper setup/approval/entry loop during the NSE regular session.
- One evaluation per finalized three-minute market-data bucket, persisted
  across restarts to prevent duplicate decisions.
- A/A+ grade, alignment-score, entry-cutoff, cooldown, open-position and
  existing risk-supervisor gates.
- Persistent automation audit history and status/run-once endpoints.
- Structured `BROKER_DATA_UNAVAILABLE` preview responses instead of HTTP 500.
- Institutional-flow summary now fails closed with `BLOCKED / NO_TRADE` when
  broker market data is unavailable, allowing safe weekend deployments.
- Explicit health fields for market-data mode, execution mode and live-order
  state.
- Shared SQLite/runtime path examples for release-safe persistence.
- Release installer excludes runtime directories before creating shared-state
  symlinks, preventing nested data/deployment links.

## Safety invariants

- `LIVE_ORDERS_ENABLED=false` is mandatory when automation is enabled.
- The worker only calls `open_paper_trade`; it never calls a broker order API.
- Closed markets, stale/missing data, weak grades, low alignment and risk
  failures produce WAITING, NO_TRADE or BLOCKED records.
- Candidate smoke-test processes force the autonomous worker off.
- A failed deployment restores the previous shared build metadata before the
  previous release is restarted.

## Activation

After deployment and smoke tests, add or update these values in
`/opt/vstradingai/shared/backend.env`:

```dotenv
LIVE_ORDERS_ENABLED=false
PAPER_AUTO_TRADER_ENABLED=true
PAPER_AUTO_TRADER_INTERVAL_SEC=15
PAPER_AUTO_TRADER_MIN_SCORE=85
PAPER_AUTO_TRADER_GRADES=A,A+
SQLITE_DB_PATH=/opt/vstradingai/shared/data/vstradingai.db
```

Restart `vstradingai-api.service`, then inspect
`/api/paper/automation/status`. Monday live-market certification remains
required before treating the generated journal as strategy evidence.
