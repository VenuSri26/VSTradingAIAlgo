# V7.5.3 — Independent Upstox Quote and Consensus Certification

V7.5.3 adds an optional, read-only Upstox V3 Full Market Quote source for
independent NIFTY 50 verification. It also evaluates accumulated shadow-mode
evidence before an operator may consider enabling mandatory source consensus.

## Safety boundary

- The adapter calls only the Upstox market-quote endpoint.
- It exposes no broker order capability.
- Missing credentials, malformed payloads, provider outages, and missing
  exchange trade timestamps produce no new evidence.
- Cached evidence retains its original exchange timestamp, so the existing
  freshness gate will age it into a degraded/stale state.
- Certification is advisory. It never changes enforcement or live-order flags.

## Configuration

```dotenv
UPSTOX_MARKET_DATA_ENABLED=false
UPSTOX_ACCESS_TOKEN=
UPSTOX_NIFTY_INSTRUMENT_KEY=NSE_INDEX|Nifty 50
UPSTOX_QUOTE_TIMEOUT_SEC=3
UPSTOX_QUOTE_POLL_INTERVAL_SEC=3

CONSENSUS_CERT_MIN_SAMPLES=500
CONSENSUS_CERT_MIN_SESSIONS=3
CONSENSUS_CERT_MIN_VERIFIED_RATIO=0.98
CONSENSUS_CERT_MAX_CONFLICT_RATIO=0.005
CONSENSUS_CERT_MAX_STALE_RATIO=0.01
CONSENSUS_CERT_MAX_P95_DEVIATION_PCT=0.08
```

Keep `MARKET_DATA_CONSENSUS_REQUIRED=false` during evidence collection.

## Inspection

- `GET /api/market-data-consensus/status`
- `GET /api/market-data-consensus/certification`
- `GET /api/market-data-consensus/history`

Promotion remains a deliberate operator decision after reviewing the sample,
session, verified/conflicted/stale ratios, and p95 price deviation.

## Research basis

- Upstox V3 Full Market Quotes: `https://upstox.com/developer/api-documentation/get-full-market-quote-v3/`
- Upstox Market Data Feed V3: `https://upstox.com/developer/api-documentation/v3/get-market-data-feed/`
- Upstox API rate limits: `https://upstox.com/developer/api-documentation/rate-limiting/`
- Zerodha quote API comparison: `https://kite.trade/docs/connect/v3/market-quotes/`
- Zerodha streaming comparison: `https://kite.trade/docs/connect/v3/websocket/`

The REST full-quote endpoint was selected for this increment because it exposes
the provider's `last_trade_time`, works within the existing polling supervisor,
and can be adopted without introducing a second WebSocket lifecycle. A V3
WebSocket adapter remains the logical later step for higher-frequency evidence.
