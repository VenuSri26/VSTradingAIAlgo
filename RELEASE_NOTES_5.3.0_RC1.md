# V5.3.0 RC1 — Consolidated Paper Lifecycle

Cumulative release based on V5.2.0 RC1. Adds restart-safe advanced paper-trade management:

- lot-aware partial exit at Target 1
- automatic break-even stop movement
- configurable percentage trailing stop
- full Target 2, trailing-stop and EOD exits
- aggregate P&L and cost accounting after partial exits
- manual close accounting after partial realization
- SQLite-persisted management state and restart recovery
- Portfolio UI for remaining quantity, active stop, high-water mark and trailing configuration

Live broker execution remains disabled.
