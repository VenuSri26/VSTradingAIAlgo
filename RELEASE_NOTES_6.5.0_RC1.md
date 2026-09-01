# V6.5.0 RC1

Cumulative release built on V6.4.0 RC1.

## Added
- Category-specific notification routing for BROKER, INFRASTRUCTURE and TRADING alerts.
- Optional WhatsApp HTTP delivery adapter with bearer-token authentication.
- Safe multi-channel notification delivery and per-channel status metrics.
- Admin-protected holiday-calendar synchronization from a configurable CSV/JSON URL.
- Live Intelligence visibility for WhatsApp and category routing.
- All live broker order execution remains disabled.

## APIs
- POST `/api/market-calendar/sync`
- Existing notification APIs now support WhatsApp and category-specific email routing.

## Validation
- Backend tests: 126 passed.
- New V6.5 tests: 4 passed.
- Python compilation: passed.
- Frontend source integrated; final npm build is an AWS deployment gate.
