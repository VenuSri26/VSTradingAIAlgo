# VSTradingAI 2.2.0 RC3 — Analytics and Decision Replay

## Added

- Realized paper-trading analytics from closed trades only.
- Equity curve and maximum drawdown series.
- Win rate, profit factor, expectancy, average win/loss and net P&L.
- CE versus PE, grade and exit-reason performance breakdowns.
- Decision replay index linking each paper trade to its generated setup.
- Complete replay with captured market/agent snapshot and monitoring timeline.
- Responsive Analytics and Replay dashboard pages.

## APIs

- `GET /api/analytics/paper`
- `GET /api/replay`
- `GET /api/replay/{trade_id}`

## Safety

- Analytics are read-only.
- Replay is read-only.
- Open trades are excluded from realized statistics.
- Live Zerodha order placement remains disabled.
