# V5.2.0 RC1 — Validated Live-to-Paper Bridge

## Included
- Converts a READY live option-chain snapshot and confirmed intraday flow trend into a draft paper setup.
- Bullish strengthening selects an ATM CE; bearish strengthening selects an ATM PE.
- Derives conservative entry band, stop loss, targets, and risk/reward.
- Requires explicit admin-token confirmation before persistence.
- Persists only a DRAFT setup; human approval remains mandatory before paper execution.
- Duplicate setup protection.
- Live broker submission remains disabled.

## APIs
- `GET /api/live-paper/preview`
- `POST /api/live-paper/prepare`
