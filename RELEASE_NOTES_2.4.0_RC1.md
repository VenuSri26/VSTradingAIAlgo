# VSTradingAI 2.4.0 RC1

Cumulative release containing Packages 1-10.

## Package 8: Zerodha live-data hardening
- Live-data health and freshness API
- Authenticated snapshot refresh
- Expiry and instrument visibility
- Safe REST polling status and reconnection counters
- No automatic broker order placement

## Package 9: Manual execution readiness
- Order preview and capital checks
- NIFTY lot-size validation
- Idempotency duplicate prevention
- Explicit `CONFIRM` gate
- Reconciliation/readiness queue
- Broker submission remains disabled unless explicitly enabled

## Package 10: Production hardening
- HTTPS enforcement switch
- Security response headers
- Application/admin token status
- Safe secret reporting
- Configuration validation for live-order switch
- Production workspace in the frontend

## Safety boundary
`LIVE_ORDERS_ENABLED=false` by default. Confirmation creates a readiness record only and does not submit to Zerodha.
