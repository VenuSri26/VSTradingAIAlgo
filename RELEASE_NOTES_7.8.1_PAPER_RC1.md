# VSTradingAI 7.8.1 Paper RC1

## Outcome

V7.8.1 adds restart-safe pre-market and post-market reports, plus read-only
Zerodha reconciliation. Live broker order placement remains disabled.

## Added

- Pre-market report scheduled for 09:00 IST on trading days.
- Post-market report scheduled for 15:40 IST on trading days.
- Persistent JSONL report history in the shared runtime data directory.
- Unified daily view of recommendations, autonomous decisions, paper trades,
  paper P&L, Zerodha orders, Zerodha trades and Zerodha positions.
- Recommendation-to-paper lineage using setup and paper-trade identifiers.
- Broker tag matching where a correlated broker order exists.
- Explicit unmatched list for manual/external Zerodha orders.
- Correlation with the durable application execution ledger by broker tag or
  broker order identifier when a controlled live execution record exists.
- Mobile-friendly report and reconciliation panel on the Auto Paper page.
- Deployment smoke coverage for readiness and trading-report endpoints.

## Safety

- Broker reconciliation only calls profile/orders/trades/positions read APIs.
- Broker payloads are persisted through an explicit field allowlist.
- No report or scheduler calls place, modify or cancel orders.
- Reports explicitly expose `PAPER_ONLY`, `READ_ONLY_REPORTING` and the
  live-order safety state.
- Pre-market reports run only before the market opens; post-market reports run
  only after it closes. Weekends and configured holidays are skipped.

## Configuration

```dotenv
TRADING_REPORT_PATH=/opt/vstradingai/shared/data/trading_reports.jsonl
TRADING_REPORT_SCHEDULER_ENABLED=true
PRE_MARKET_REPORT_TIME=09:00
POST_MARKET_REPORT_TIME=15:40
TRADING_REPORT_POLL_INTERVAL_SEC=60
```

The Monday live-session requirement remains unchanged: refresh the Zerodha
token, confirm the loop and monitor are running, and keep
`LIVE_ORDERS_ENABLED=false`.
