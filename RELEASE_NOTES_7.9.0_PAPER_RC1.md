# VSTradingAI 7.9.0 Paper RC1

## Verdict

V7.9.0 is the preferred offline and supervised paper-certification release. It is **not approved for live orders** and is not yet certified for unattended market operation. `LIVE_ORDERS_ENABLED=false` remains mandatory.

## Connected decision path

The automatic paper worker no longer relies on the OI/PCR preview alone. With the default `PAPER_REQUIRE_FULL_PIPELINE=true`, a candidate must also pass the full indicator and multi-agent pipeline:

1. timezone-aware completed 3-minute data;
2. feature, regime, trend, momentum, liquidity, option/OI, gamma and trap agents;
3. coverage/disagreement and A/A+ grade;
4. risk-agent approval;
5. direction agreement with the live OI/PCR candidate;
6. verified `decision-evidence/v1` certificate;
7. option bid/ask, spread, OI, volume and freshness gates;
8. persistent risk supervisor and paper ledger.

Any conflict becomes `NO_TRADE/BLOCKED` with explicit reason codes. The operator page shows the corroborating full-pipeline decision and grade.

## Cost realism

`INDIA_OPTIONS_V1` replaces the opaque flat cost estimate for managed paper exits. It itemizes configurable brokerage, STT on sell premium, exchange charges, SEBI charges, buy-side stamp duty and GST. These are simulation assumptions and must be reviewed against the active broker/exchange schedule before interpreting net P&L.

## Safety improvements

- The full pipeline independently removes an actively forming 3-minute row before feature calculation.
- Its evidence certificate must bind the decision to a finalized bar.
- Readiness now fails if full-pipeline corroboration is disabled.
- Readiness fails if Kite WebSocket is requested while the pinned Autobahn security blocker remains.
- Live order behavior was not added or enabled.

## Verification

- Backend: `278 passed, 1 warning in 2.64s`.
- New V7.9 orchestrator/cost tests: included in the full count.
- Frontend TypeScript/Vite production build: passed, 55 modules.
- Python compilation: passed.
- Runtime/startup and dependency scans are recorded in `TEST_REPORT_7.9.0.md`.

## Remaining acceptance blockers

- No authenticated Zerodha market session was available in the audit environment.
- The Zerodha SDK still pins vulnerable `autobahn==19.11.2`; WebSocket remains disabled.
- Fee rates require operator review whenever official schedules change.
- At least five full supervised market sessions are required before unattended paper activation.
- No profitability, win-rate or fill-quality claim is made.
