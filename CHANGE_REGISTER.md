
## 1.9.0 - 2026-08-02

- Added restart-safe automated paper-trade monitoring.
- Added Zerodha/mock option quote refresh for the open paper trade.
- Added automatic SL, T1, T2 and configurable EOD paper exits.
- Added persistent monitor event history and local JSONL notification outbox.
- Added monitor status, event history and protected run-once APIs.
- Confirmed that no live Zerodha order method is called by the monitor.

# VSTradingAI Change & Improvement Register

This is the verification record for every production-facing change. New entries must be appended; previous entries must not be rewritten except to correct a factual error, which must itself be noted.

## CR-2026-08-02-001 — Version 1.1.0 Audit, Backup and Rollback Foundation

| Field | Record |
|---|---|
| Date | 2026-08-02 |
| Version | 1.1.0 |
| Category | Reliability, auditability, deployment safety |
| Requested outcome | Track all improvements so they can be verified later and make future AWS changes reversible |
| Modules/files | `VERSION`, `CHANGELOG.md`, `CHANGE_REGISTER.md`, `backend/app/version.py`, `backend/app/main.py`, `backend/app/routes.py`, AWS install/test/backup/rollback scripts, deployment documentation |
| Trading logic impact | None |
| Zerodha compatibility | Preserved; no Kite API contract or credential behavior changed |
| API compatibility | Additive only: version/build fields and a new version endpoint |
| Data compatibility | Existing SQLite and audit-log paths preserved |
| Security impact | Backups exclude `.env` by default from distributable archives; server backups protect it with root-only permissions |
| Tests | Compile, pytest, legacy verifiers, API smoke tests, shell syntax checks |
| Rollback | Run `sudo /opt/vstradingai/rollback_aws_lightsail.sh --list`, then restore the chosen backup |
| Pending follow-up | Cached decision snapshot service; Zerodha instrument cache; setup lifecycle persistence; paper-trading engine |

## Mandatory template for future entries

```text
Change ID:
Date:
Version:
Category:
Problem / objective:
Files and modules changed:
Implementation summary:
Trading logic impact:
Zerodha compatibility impact:
API / database compatibility impact:
Configuration changes:
Tests executed:
Test results:
AWS deployment notes:
Rollback procedure:
Known limitations:
Pending follow-up:
Approver / verifier:
```

## CR-2026-08-02-002 — Version 1.2.0 Zerodha Data Reliability

| Field | Record |
|---|---|
| Date | 2026-08-02 |
| Version | 1.2.0 (included in consolidated 1.3.0 package) |
| Category | Zerodha reliability and market-data integrity |
| Problem / objective | Reduce instrument API load, expose token health, reject expired contracts, and stop presenting invalid OI-change values |
| Files and modules changed | `backend/app/data_sources/zerodha_client.py`, `backend/app/routes.py`, environment documentation |
| Trading logic impact | Conservative: OI-change-dependent evidence is unavailable rather than incorrectly calculated |
| Zerodha compatibility impact | Uses official Kite methods only; no credential format or order API changes |
| API / database compatibility impact | Additive `/api/system/zerodha-health` endpoint |
| Tests executed | Compilation, pytest, legacy verifiers, API smoke checks |
| Rollback procedure | Restore the pre-deployment 1.1.0 AWS backup |
| Known limitations | Previous-session OI baseline is not yet persisted |

## CR-2026-08-02-003 — Version 1.3.0 Paper-Setup Lifecycle Foundation

| Field | Record |
|---|---|
| Date | 2026-08-02 |
| Version | 1.3.0 |
| Category | Paper trading, auditability, human approval |
| Problem / objective | Persist actionable decisions and provide a verifiable approval/rejection lifecycle without automatic broker execution |
| Files and modules changed | `backend/app/store.py`, `backend/app/routes.py`, `backend/tests/test_trade_setups.py`, version and release documents |
| Trading logic impact | None; only actionable output persistence and review workflow were added |
| Zerodha compatibility impact | Preserved; broker execution remains disabled and human-in-the-loop |
| API / database compatibility impact | Additive SQLite table and additive `/api/setups` APIs |
| Tests executed | Compilation, pytest, legacy verifiers, shell checks and API smoke tests |
| Rollback procedure | Use `/opt/vstradingai/rollback_aws_lightsail.sh` to restore the prior backup |
| Pending follow-up | Virtual fills, execution-cost model, SL/T1/T2 monitor, end-of-day closure and paper-trade report |

## CR-2026-08-02-004 — Version 1.4.0 Paper Execution and Risk Engine
- **Reason:** Extend the approved-setup workflow into measurable paper execution without enabling broker orders.
- **Files/modules:** `backend/app/store.py`, `backend/app/routes.py`, `backend/app/config.py`, `backend/.env.example`, `backend/tests/test_paper_execution.py`, version and release documentation.
- **Implementation:** Added persistent `paper_trades`; risk-sized paper entries; configurable slippage/cost estimates; stop, target and EOD exit monitoring; session P&L update on closure.
- **Compatibility:** Existing API routes and Zerodha data-source interfaces remain intact. Database migration is additive (`CREATE TABLE IF NOT EXISTS`).
- **Broker impact:** None. Zerodha remains data-only/manual execution; automatic broker order placement remains disabled.
- **Tests:** Python compile passed; pytest 15 passed; legacy verification 88 passed; API/version smoke tests passed; AWS shell syntax passed.
- **Rollback:** Use `rollback_aws_lightsail.sh`; prior database remains readable because changes are additive. Restore the pre-deployment backup to remove v1.4 runtime data.
- **Follow-up:** Add automated scheduled monitor, partial exits/trailing stop, and broker-verified charge calculator only after paper evidence is available.

## CR-2026-08-02-1.5.0 — Historical Replay and Strategy Validation
- **Version:** 1.5.0
- **Date:** 2026-08-02
- **Reason:** Establish conservative, reproducible strategy validation before expanding paper or live execution.
- **Files/modules:** `backend/app/strategy_validation.py`, `backend/tests/test_strategy_validation.py`, `backend/scripts_validate_strategy.py`, `VERSION`, `CHANGELOG.md`, documentation and validation report.
- **Implementation:** Next-bar entry, pessimistic same-bar conflict handling, costs/slippage, time exits, performance metrics, regime analysis and expanding walk-forward splits.
- **Backward compatibility:** Existing API routes, dashboard, paper engine and configuration remain unchanged.
- **Zerodha compatibility:** No Kite API contract changes. Engine accepts generic chronological OHLC data and can later consume Zerodha historical candles.
- **Trading impact:** None. This module cannot alter agent weights, approve setups or place orders.
- **Rollback:** Restore the automatic pre-deployment backup or deploy the v1.4.0 package.
- **Pending:** Historical Nifty option premium archive, strategy-specific signal adapter, downloadable HTML validation report and parameter stability heatmaps.


## CR-2026-08-02-1.6.0 — Multi-Agent Confidence and Debate Engine
- **Version:** 1.6.0
- **Date:** 2026-08-02
- **Reason:** Prevent false confidence caused by unavailable agents, correlated evidence, and balanced bull/bear disagreement.
- **Modules changed:** `app/agents/alignment.py`, `app/agents/debate.py`, `app/models.py`, `app/schemas.py`, `app/pipeline.py`, `app/config.py`, `.env.example`, tests and release documentation.
- **Implementation:** Added deterministic debate cases, evidence-family mapping/caps, coverage ratio, disagreement score, calibrated confidence, regime multipliers, and conservative grade gates.
- **Backward compatibility:** Additive response fields only. Existing endpoints and core agent signatures remain compatible. Decision qualification may be more conservative by design.
- **Zerodha impact:** None. Data-source and order-wrapper contracts were not changed; live auto-execution remains disabled.
- **Tests:** Python compilation, 25 pytest tests, legacy verification scripts, API smoke tests, and AWS shell syntax checks.
- **Rollback:** Restore the v1.5.0 AWS backup using `rollback_aws_lightsail.sh`; no database migration is required.
- **Pending:** Dashboard visualization of debate/coverage, confidence calibration using larger paper-trade datasets, and configurable family caps through admin settings.


## CR-2026-08-02-1.7.0 — Production Monitoring and Operations

- **Version:** 1.7.0
- **Date:** 2026-08-02
- **Reason:** Improve production visibility, recovery readiness and AWS operational verification without modifying trading decisions.
- **Files/modules changed:** `app/observability.py`, `app/main.py`, `app/routes.py`, `app/config.py`, `.env.example`, AWS installation/testing scripts, `daily_health_report.sh`, `operations_check.sh`, tests and release documentation.
- **Implementation:** Added structured JSON logs, request and pipeline identifiers, in-memory operational metrics, alert history, health-report generation, daily backups and systemd timers.
- **Trading impact:** None. Agent calculations, decision gates, paper execution and historical validation are unchanged.
- **Zerodha compatibility:** No Kite API request, response or authentication behavior changed.
- **Backward compatibility:** Existing REST and WebSocket endpoints remain available; new endpoints are additive.
- **Tests:** Python compilation passed; 27 pytest tests passed; 88 legacy verification checks passed; shell syntax passed; API smoke tests passed.
- **Deployment:** Existing installer enables daily health-report and backup timers. Review timer status with `systemctl list-timers`.
- **Rollback:** Restore the pre-deployment backup using `rollback_aws_lightsail.sh`; no database migration is required.
- **Pending:** Persistent external metrics backend, notification delivery and log rotation policy can be added after AWS observation.

## CR-1.8.0 — Dashboard Operations and Paper Controls
- Date: 2026-08-02
- Reason: Surface operational health and existing paper lifecycle safely in the frontend.
- Files: frontend/src/Dashboard.tsx, cards/OperationsCards.tsx, services/api.ts, types/operations.ts, Vite/TypeScript scaffolding, release docs.
- Compatibility: Additive frontend release; backend endpoints and Zerodha contracts unchanged.
- Safety: ADMIN_TOKEN remains required for mutations; token is sessionStorage-only; automatic/live Zerodha execution remains disabled.
- Rollback: restore v1.7.0 backup/package; no database migration.

## Change Record: 2.0.0 — Deployment Assurance and Clean Release Engineering
- Date: 2026-08-02
- Type: Infrastructure, release engineering, database governance
- Trading logic impact: None
- Zerodha execution impact: None; live order execution remains disabled
- Main changes: clean packaging, synchronized versions, dependency lock, AWS preflight, staged release installation, candidate validation, automatic rollback, migration tracking, post-deployment smoke tests, read-only Zerodha validation.
- Compatibility: Existing SQLite schema and APIs retained. Shared runtime data is preserved between releases.
- Rollback: `current` symlink is returned to the previous release when post-deployment smoke testing fails.
- Validation: Python compilation, pytest, legacy verification scripts, shell syntax, version consistency, package hygiene, migration registration, API smoke checks.

## CHG-2.2-RC2 — Paper Trading and Risk Supervisor
- **Version:** 2.2.0-rc.2
- **Reason:** Complete Package 2 and Package 3 before AWS validation.
- **Modules:** store, routes, risk_supervisor, config, migrations, frontend API/types/risk page.
- **Compatibility:** Existing APIs preserved; new APIs are additive.
- **Zerodha impact:** Read-only market data only; live execution remains disabled.
- **Rollback:** Restore the prior release symlink. Migration adds only the risk_state table.

## CHG-2.2-RC3 — Analytics and Decision Replay

- **Date:** 2026-08-03
- **Version:** 2.2.0-rc.3
- **Reason:** Provide evidence-based evaluation of paper trades and make every decision auditable.
- **Backend:** Added realized paper analytics, equity/drawdown calculations, performance breakdowns and replay queries.
- **Frontend:** Added professional Analytics and Replay workspaces.
- **Database:** No destructive migration. Existing setup snapshot and monitor-event data are reused.
- **Zerodha impact:** None. Read-only analytics only.
- **Backward compatibility:** Existing APIs preserved.
- **Tests:** 35 pytest tests passed; 88 legacy verification checks passed; shell syntax passed; route registration passed.
- **Rollback:** Restore the previous 2.2.0-rc.2 release. No schema rollback is required.

## CHG-2.3.0-RC1 — Packages 5, 6 and 7
- Modules: Operations, Multi-Agent visibility, Strategy Lab.
- Compatibility: additive APIs and UI pages; existing routes retained.
- Zerodha impact: read-only health/data behavior only; no order behavior changes.
- Rollback: application rollback is safe; no destructive database migration.
- Validation: Python compilation, pytest, legacy verification scripts, shell syntax and source localhost scan.

## V2.5.0-RC1 — Live Market Data and Broker Readiness

- **CHG-2501** Added restart-safe persisted market-data supervisor.
- **CHG-2502** Added token/session health and poll recovery metrics.
- **CHG-2503** Added instrument-master synchronization and status API.
- **CHG-2504** Added 3-minute spot candle aggregation.
- **CHG-2505** Added safe NO_TRADE fallback for stale/unavailable data.
- **CHG-2506** Expanded Production workspace with feed-quality controls.
- **Safety:** Live order placement remains disabled.
- **Rollback:** No database migration; restore V2.4.0 stable release symlink.

| CHG-2702-01 | Institutional Flow | Persist session snapshots and PCR/flow history | Historical evidence and trend validation | 57 tests | AWS pending | Complete |
| CHG-2702-02 | Decision Engine | Add flow-adjusted decision intelligence endpoint | Surface confirmation/conflict without changing order logic | 57 tests | AWS pending | Complete |
| CHG-2702-03 | Replay | Attach nearest institutional-flow evidence | Improve post-trade evidence review | 57 tests | AWS pending | Complete |
| CHG-2702-04 | Frontend | Add flow trend/anomaly dashboard | Make session changes visible | Backend validated; AWS build pending | AWS pending | Complete |

## 5.1.0-rc.1
- Added restart-safe SQLite persistence for live option-chain intelligence.
- Added intraday PCR, CE OI and PE OI history/trend APIs.
- Added OI trend visualization to the Live Intelligence workspace.
- Added migration 006_live_intelligence_history.sql and regression tests.

### V6.8.0 RC1
- Multi-session certification evidence gate.
- Certification report notification outbox integration.
- Four new backend tests; full suite 137 passed.

## V7.3.1 — Fail-Closed Input Integrity

- **Date:** 2026-09-15
- **Reason:** Remove silent timestamp substitution and prevent unverifiable option quotes or reset volume counters from contaminating execution evidence.
- **Modules:** `live_market_stream.py`, `data_quality_gate.py`, and focused regression tests.
- **Safety:** Broker ticks without a valid exchange timestamp or positive finite price are rejected; missing option quote timestamps block execution; cumulative-volume resets are rebased without inflating candle volume.
- **Trading impact:** No strategy or broker-write behavior added. Mock mode and disabled live orders remain the defaults.
- **Validation:** 9 focused integrity tests and 180 full backend tests passed; frontend production build passed; npm audit found 0 vulnerabilities; `git diff --check` passed.
- **Rollback:** Revert this single additive checkpoint; no schema or data migration is required.

## V7.3.2 — Finalized 3-Minute Candle Integrity

- **Date:** 2026-09-15
- **Reason:** Prevent polling timestamps, duplicate samples, or delayed samples from altering decision candles.
- **Modules:** `market_data_service.py` and focused market-data regression tests.
- **Safety:** Exchange timestamps are mandatory and timezone-aware; missing, invalid, or future timestamps activate `NO_TRADE`; duplicate and out-of-order samples cannot mutate OHLC; decision consumers receive finalized 3-minute candles only.
- **Trading impact:** No strategy thresholds or broker-write behavior changed. Mock mode and disabled live orders remain the defaults.
- **Compatibility:** Existing candle fields remain available; the additive `finalized` field explicitly distinguishes closed bars, and supervisor snapshots intentionally exclude the forming bar.
- **Validation:** 16 focused integrity tests and 184 full backend tests passed; frontend production build passed; npm audit found 0 vulnerabilities; `git diff --check` passed.
- **Rollback:** Revert this single checkpoint; no schema or persisted-data migration is required.
