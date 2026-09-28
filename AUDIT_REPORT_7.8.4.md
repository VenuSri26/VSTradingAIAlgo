# VSTradingAI 7.8.4 adversarial audit

Audit date: 2026-09-26 UTC  
Input archive SHA-256: `0b876d52b7a10892958654934e1d8aea8342aefa61264fa26ac5cafc902c60c8`  
Input version: `7.8.3-paper-rc1`  
Audited version: `7.8.4-audit-rc1`

## Executive verdict

**NOT READY for unattended automated paper trading.** It is suitable for offline deterministic paper-loop evaluation and supervised REST-polling trials with `LIVE_ORDERS_ENABLED=false`. The backend starts, 273 tests pass after this audit, the frontend builds, and the deterministic paper lifecycle is exercised. Readiness remains blocked by an obsolete vulnerable WebSocket dependency forced by the Zerodha SDK, absence of a verified live-market session in this environment, a simplified cost/fill model, and incomplete proof that the autonomous path uses the full strategy/agent pipeline.

Strongest parts: fail-closed configuration, persistent paper ledger, risk supervisor, restart reconciliation, broad API surface and test coverage. Critical weaknesses: the pre-audit automatic path inferred a candle from an option-chain timestamp, selected contracts without spread/liquidity gates, and shipped runtime databases and backup source files. These were corrected or quarantined. Residual risk is explicitly listed below.

## Evidence classification

- **Observed:** 375 files, Python/FastAPI backend, React/TypeScript/Vite frontend, SQLite persistence, deployment scripts, no Git metadata in the supplied ZIP.
- **Test verified:** application startup; paper-only health; finalized-candle, stale/auth failure, deduplication, risk, restart, journal and deterministic lifecycle tests; frontend production build.
- **Inferred:** AWS behavior from scripts and service definitions; not deployed during this audit.
- **Not verifiable here:** real Zerodha session, NSE live tick ordering, actual exchange holiday feed, a full market-day soak, broker throttling, or AWS restart behavior.

## Current-state capability matrix

| Feature | Before | Evidence | Change | After / evidence |
|---|---|---|---|---|
| Live-order safety | Present | config and health default false | Preserved | Verified runtime `false` |
| Zerodha auth | Present | health/API/tests | No secret used | Offline tests only; live unverified |
| 3-minute finalization | Disconnected from auto loop | option timestamp used as cycle key | Explicit aligned, completed OHLC required | Verified by rejection test |
| Holiday control | Admin file disconnected | auto loop read env list only | Union env and validated managed file; corrupt file blocks | Verified by two tests |
| Option liquidity | Missing in auto selection | any positive LTP accepted | bid/ask, spread, OI, volume gates; ask-side entry | Verified wide-spread rejection |
| Duplicate suppression | Present | durable cycle table | Candle start is cycle key | Verified deterministic test |
| Paper lifecycle | Present | ledger/monitor/journal | Snapshot/version and price excursions added | E2E test verified |
| Journal quality | Partial | no entry slippage/MFE/MAE | migration and calculations | Verified in E2E test |
| Restart recovery | Present | persisted open trade | lowest price persisted | Tests pass |
| UI | Present | React routes/components | Version updated | Vite build succeeds |
| Dependency security | Unsafe | 33 initial findings | upgraded maintained direct deps | 3 findings remain in forced Autobahn |
| Repository hygiene | Unsafe | runtime DB/logs and source backups shipped | removed from release, retained in audit quarantine | Final scan required |

## Architecture assessment

Current verified flow is: configuration safety -> session/calendar -> broker/data boundary -> finalized candle -> live-intelligence candidate -> liquidity and confidence gates -> risk supervisor -> persistent paper setup/trade -> monitor -> journal/API/UI. The larger indicator, structure and multi-agent pipeline exists, but the autonomous paper worker does not prove full end-to-end use of every engine; those labels must not be treated as execution evidence.

Failure boundaries are broker auth, market data freshness/completeness, calendar validity, candle finality, option liquidity, risk state, persistence and UI freshness. Each must independently block trading. No aggregate health flag should override a failed component.

## Prioritized findings

| ID | Severity | Problem / evidence | Resolution or status |
|---|---|---|---|
| F-001 | P0 | Runtime databases/logs and backup source files shipped in input | Quarantined and excluded from final ZIP |
| F-002 | P0 | Zerodha SDK pins vulnerable `autobahn==19.11.2` | **Open blocker:** keep WebSocket disabled; isolate/replace SDK before enabling |
| F-003 | P1 | Automatic cycle used option timestamp, not a completed candle | Fixed and tested |
| F-004 | P1 | Automatic strike selection ignored bid/ask, spread, OI and volume | Fixed and tested |
| F-005 | P1 | Managed holiday calendar was disconnected from auto loop | Fixed fail-closed and tested |
| F-006 | P1 | Autonomous loop not proven to execute full strategy/agent pipeline | Open blocker; connect one versioned orchestrator and certify it |
| F-007 | P1 | No live Zerodha/NSE session could be certified | Open environmental blocker |
| F-008 | P1 | Cost/fill model lacks complete Indian fee breakup and probabilistic partial fills | Open; paper results must not be presented as realistic performance |
| F-009 | P2 | Journal omitted explicit entry slippage and price excursions | Fixed with migration/tests |
| F-010 | P2 | README/history contains broad claims not supported by current execution path | Retained for compatibility; this audit is authoritative |

## Failure-scenario result summary

Expired/missing auth, stale data, unfinalized candles, duplicate cycles, market closure, holiday, corrupt calendar, wide spreads, low liquidity, risk rejection, kill switch, restart reconciliation, and duplicate paper orders have fail-closed automated coverage. HTTP 429/500, out-of-order live ticks, database corruption, shortened sessions, full tax computation, partial fills and complete frontend stale-state behavior remain partially covered or unverified. See `TEST_REPORT_7.8.4.md` for commands.

## Trading-readiness checklist

- Zerodha authentication: **offline behavior passes; live session unverified**
- Live data freshness: **gated; live soak unverified**
- Completed candles: **pass**
- Strategy evaluation: **partial; full orchestrator not connected to auto loop**
- Risk gates/kill switch: **pass in tests**
- Paper execution/journal/restart: **pass in deterministic tests**
- Pre/post-market reports: **present and unit-tested; live-day output unverified**
- UI visibility: **build passes; browser/live-state acceptance unverified**
- Live orders disabled: **pass in configuration and runtime smoke**

Shortest safe path: keep REST polling and supervised paper mode, resolve the Autobahn/Kite dependency boundary, connect the versioned full decision pipeline to a single replayable orchestrator, implement India-specific fees/fills, then run at least five complete market-day shadow sessions before reconsidering readiness.
