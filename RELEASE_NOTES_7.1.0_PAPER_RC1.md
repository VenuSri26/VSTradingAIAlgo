# V7.1.0 PAPER RC1

Built on the verified V7 stable live Zerodha baseline.

## Already present and retained
- Paper-only execution behind ADMIN_TOKEN and risk supervisor
- One-open-paper-trade guard
- Restart-safe SQLite ledger
- Automated option-price monitor (default every 5 seconds)
- SL, Target-2 and 15:20 EOD exits
- Target-1 partial profit, break-even stop and optional trailing stop
- Estimated slippage/cost accounting
- Paper portfolio, analytics, equity curve, replay and timeline
- Tick-to-paper bridge and human-review setup bridge
- Live broker orders remain disabled

## Added in RC1
- Enriched paper journal API: `/api/paper/journal`
- Downloadable CSV journal: `/api/paper/journal.csv`
- Daily paper summary: `/api/paper/daily-summary`
- Journal includes setup grade/alignment/explanation, management state and monitor-event count
- Installation and smoke-test scripts for AWS
