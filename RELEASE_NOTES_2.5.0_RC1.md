# VSTradingAI 2.5.0 RC1

Live Market Data and Broker Readiness release built on V2.4.0 stable.

## Included
- Restart-safe persisted market-data supervisor.
- Safe REST polling foundation for Zerodha and mock modes.
- Token/session status without exposing secrets.
- Instrument-master synchronization.
- Quote age, poll success, failure and recovery metrics.
- 3-minute candle aggregation.
- Automatic safe NO_TRADE state when data is stale or unavailable.
- Production dashboard controls for manual poll and instrument sync.

## Safety
- `LIVE_ORDERS_ENABLED=false` remains the default.
- No automatic broker order submission was added.
- `KITE_WEBSOCKET_REQUESTED=false` remains the default; REST polling is used safely.
