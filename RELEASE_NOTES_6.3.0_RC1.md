# V6.3.0 RC1 — Operational Digest and Severity Routing

Baseline: V6.2.0 RC1 (cumulative)

## Added
- Persistent daily operational digest history.
- Consolidated notification, scheduler, holiday-calendar and broker-Greeks readiness report.
- Generate-and-queue digest endpoint protected by the admin token.
- Severity-specific SMTP recipient routing with fallback to the default recipient list.
- Live Intelligence dashboard digest panel and recent digest history.
- Safety invariant: live broker orders remain disabled.

## APIs
- GET /api/operations/digest/status
- GET /api/operations/digest/history
- POST /api/operations/digest/generate?enqueue=true

## Validation
- 118 backend tests passed.
- Python compilation passed.
- Deployment shell syntax passed.
- Frontend source integrated; final AWS build remains mandatory because the internal packaging registry lacks @types/react-dom@18.3.0.
