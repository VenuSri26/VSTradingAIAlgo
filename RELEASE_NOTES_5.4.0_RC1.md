# V5.4.0 RC1 — Market Session & Feed Safety

Cumulative release built on V5.3.0 RC1.

## Added
- India-market timestamp normalization.
- Weekend, holiday, pre-open and post-close session checks.
- Feed watchdog with stale-data, authentication and failure blocking.
- WebSocket-requested / REST-fallback visibility.
- Token-health age warning.
- Instrument/expiry readiness warnings.
- Live Intelligence dashboard safety panel.
- Market safety APIs and deterministic tests.

## Safety
- Decision support is blocked when market data is stale, disconnected or unauthenticated.
- Live order submission remains disabled.
