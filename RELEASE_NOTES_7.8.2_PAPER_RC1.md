# VSTradingAI 7.8.2 Paper RC1

## Outcome

V7.8.2 adds a safe browser Setup console for paper-trading configuration and
Zerodha authentication. Live broker orders remain locked off.

## Setup console

- Shows Zerodha connection status without returning API keys or access tokens.
- Starts the official Zerodha login flow and accepts the complete redirect URL.
- Requires HTTPS before a redirect URL can be submitted.
- Keeps execution in `PAPER_ONLY`; the UI cannot enable live orders.
- Configures confidence from 70–90, capital from ₹10,000–₹2,00,000, a
  profit-withdrawal alert threshold and the default paper stop-loss percentage.
- Saves values to the shared backend environment with mode `0600` and creates a
  timestamped backup before each update.

## Trading behavior

- The stop-loss percentage applies to new paper positions.
- The withdrawal value is an alert threshold only; the system never moves money.
- Existing open paper positions retain their original stop-loss.
- Live execution requires a separate future approval and is not exposed here.

## Configuration

```dotenv
PAPER_AUTO_TRADER_MIN_SCORE=85
PAPER_CAPITAL=10000
PAPER_PROFIT_WITHDRAWAL_THRESHOLD=100000
PAPER_DEFAULT_STOP_LOSS_PCT=20
LIVE_ORDERS_ENABLED=false
```

For browser token refresh, terminate TLS at Nginx and ensure the application
receives `X-Forwarded-Proto: https`. Until HTTPS is configured, use the existing
server-side `vstradingai-refresh-kite-token` command.
