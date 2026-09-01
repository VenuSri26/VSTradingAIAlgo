# VSTradingAI 3.1.0 RC1

Cumulative release built on V3.0.0 RC1.

## Added
- Operational resilience and restart-safety engine.
- SQLite availability and persistence checks.
- Audit-log directory writeability check.
- Market-data recovery-state validation.
- Open paper-position recovery verification.
- Automatic live-order safety-lock verification.
- `/api/resilience/status` and `/api/resilience/restart-check`.
- Resilience dashboard page with 15-second refresh.

## Safety
- Paper-only default is preserved.
- No automatic broker order submission was added.
- Existing V2.8, V2.9 and V3.0 features are retained.
