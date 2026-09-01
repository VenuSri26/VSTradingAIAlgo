# VSTradingAI 7.0.0 Alpha 3 — Live Tick & Candle Pipeline

Baseline: V7.0.0 Alpha 2 live-market gateway.

## Implemented

- Thread-safe broker tick cache fed by KiteTicker callbacks.
- NIFTY and India VIX included in automatic runtime subscriptions.
- NIFTY 1m, 3m and 5m candles built directly from received ticks.
- Duplicate market simulation is not introduced: missing live ticks remain unavailable.
- Completed-candle indicator API for EMA20/50, RSI, MACD, ATR, ADX and VWAP.
- During WebSocket warm-up, indicators explicitly use completed Zerodha historical OHLC; never mock data when live mode is active.
- New real-time feed/tick/candle/indicator APIs.
- Live Intelligence page polls the V7 feed every 3 seconds and shows broker tick status and indicator provenance.
- NIFTY/VIX ticks are not routed into option paper-trade monitoring.
- Option ticks continue through the existing paper management bridge.
- Live orders remain disabled.

## New APIs

- `GET /api/live-market/feed`
- `GET /api/live-market/ticks`
- `GET /api/live-market/candles`
- `GET /api/live-market/indicators`

## Safety

`LIVE_ORDERS_ENABLED` is not used to place orders by this package. All new code is market-data/read-model logic only.
