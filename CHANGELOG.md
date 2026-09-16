# Changelog

## 2.6.0-rc.2
- Removed hardcoded frontend version badge; UI now reads `/api/system/version`.
- Added build ID, build time, commit, environment and active release metadata.
- Added release certificate and production health score.
- Added decision explainability checklist, blockers and invalidation conditions.
- Persisted the last successful smoke-test record.
- Preserved V2.6 RC1 option-chain intelligence and all cumulative V2.5/V2.4 features.

## 2.0.0 - 2026-08-02

### Deployment assurance
- Added clean release packaging with runtime data exclusion.
- Synchronized root and frontend versions.
- Added pinned backend lock file and npm clean-build support.
- Added Ubuntu/AWS preflight validation.
- Added staged releases under `/opt/vstradingai/releases` with a `current` symlink.
- Added candidate startup on port 8001 before production cutover.
- Added automatic rollback when post-deployment smoke tests fail.
- Added versioned SQLite migration tracking.
- Added Zerodha read-only validation and Docker parity validation assets.


## 1.9.0 - 2026-08-02

- Added restart-safe automated paper-trade monitoring.
- Added Zerodha/mock option quote refresh for the open paper trade.
- Added automatic SL, T1, T2 and configurable EOD paper exits.
- Added persistent monitor event history and local JSONL notification outbox.
- Added monitor status, event history and protected run-once APIs.
- Confirmed that no live Zerodha order method is called by the monitor.

# Changelog

## [1.7.0] - 2026-08-02

### Added
- JSON structured application and request logging with request IDs.
- Pipeline metrics for latency, success rate, failures, decisions and stale-data events.
- Operational alert history for pipeline failures, stale data and RED health.
- `/api/system/metrics` and `/api/system/alerts` endpoints.
- Daily AWS health-report script and systemd timer.
- Daily checksum-protected AWS backup timer.
- Operations check script and expanded AWS validation.

### Compatibility
- No Zerodha API or order-execution contract changes.
- No trading formula, agent score, risk threshold or database schema changes.
- Automatic Zerodha execution remains disabled.

## [1.6.0] - 2026-08-02
### Added
- Deterministic bull/bear debate summary from existing agents.
- Agent coverage ratio and disagreement score.
- Confidence calibration that penalizes missing evidence and disagreement.
- Evidence-family caps to reduce double-counting correlated indicators.
- Regime-aware family weight multipliers.
- Configurable minimum coverage and maximum disagreement gates.
- Five focused tests for the multi-agent confidence controls.

### Safety and compatibility
- No Zerodha order-placement behavior was enabled or changed.
- Existing REST fields remain available; new alignment and debate fields are additive.
- A/A+ decisions are now more conservative when evidence coverage is weak or agents disagree.

All notable VSTradingAI changes are recorded here. The project follows semantic versioning.

## [1.1.0] - 2026-08-02

### Added
- Formal `VERSION`, `CHANGELOG.md`, and `CHANGE_REGISTER.md` files.
- Runtime build/version metadata exposed by `/healthz`, `/api/system/version`, and `/api/system/config-check`.
- `backup_aws_lightsail.sh` for safe application and persistent-data backups.
- `rollback_aws_lightsail.sh` for restoring a selected deployment backup.
- Pre-deployment backup and deployment history recording in the AWS installer.
- Validation report generation in `deployment/validation/`.
- Deployment manifest with source version, timestamp, host, and validation result.

### Changed
- FastAPI application version now comes from the canonical project version.
- AWS validation checks version consistency, backup/rollback script syntax, service state, and core APIs.
- Installation excludes local secrets, virtual environments, runtime databases, logs, and caches from source copying.

### Compatibility
- No trading strategy, agent-weight, signal, risk-decision, Zerodha API, or frontend response field was removed.
- Existing endpoints remain compatible; version fields are additive.
- Automatic broker order execution remains disabled.

### Validation
- Python compilation.
- Pytest suite.
- Legacy verification scripts.
- FastAPI endpoint checks in mock mode.
- AWS shell-script syntax checks.

## 1.3.0 — 2026-08-02

### Added
- Zerodha session-health endpoint for AWS and dashboard checks.
- Daily in-memory NFO instrument-master cache with safe stale-cache fallback.
- Expired-contract exclusion and tradingsymbol/instrument-token metadata.
- Persistent trade-setup lifecycle (`GENERATED`, `APPROVED`, `REJECTED`, `EXPIRED`, `CANCELLED`).
- Setup listing and protected human-review APIs.
- Automated persistence of actionable generated setups without enabling broker execution.

### Corrected
- Removed the incorrect use of `oi_day_high` as change in open interest. OI change is now explicitly unavailable until a valid baseline exists.

### Compatibility
- Existing APIs and SQLite data remain compatible; schema additions are additive.
- Zerodha automatic order placement remains disabled.

## [1.4.0] - 2026-08-02
### Added
- Paper-only execution endpoint for human-approved setups.
- Capital and percentage-risk based position sizing with Nifty lot-size enforcement.
- Configurable paper slippage and estimated transaction-cost model.
- Persistent paper trade lifecycle and audit records.
- Stop-loss, Target 1, Target 2, and forced end-of-day monitoring/closure.
- Paper-trade listing endpoint and lifecycle tests.

### Safety
- No Zerodha order placement was enabled or changed.
- Paper execution requires an APPROVED setup and protected admin endpoint.

## [1.5.0] - 2026-08-02
### Added
- Conservative historical replay engine with strict next-bar execution.
- Same-candle stop/target ambiguity resolved pessimistically as stop-loss.
- Configurable slippage, transaction-cost, quantity and holding-period modelling.
- Performance metrics including expectancy, profit factor, drawdown and regime breakdown.
- Expanding walk-forward train/test split generator with chronological leakage protection.
- CSV validation command and dedicated automated tests.

### Safety and compatibility
- No changes to live signal generation, Zerodha APIs or broker execution.
- Validation output is descriptive only and cannot automatically promote a strategy.

## [1.8.0] - 2026-08-02
### Added
- Operations dashboard with production metrics, recent alerts, Zerodha health and deployed version.
- Human-reviewed setup approval/rejection controls protected by ADMIN_TOKEN.
- Paper execution and paper monitoring controls; no live broker order path.
- Strong frontend API types, request timeout, error details and complete Vite build scaffolding.

## [2.2.0-rc.1] - 2026-08-03

### Added
- Responsive application shell with sidebar and mobile navigation.
- Dedicated Trading, Portfolio, Analytics, Operations, and Settings workspaces.
- Paper-trade journal summary and portfolio metrics page.
- Operations Console separated from the market overview.
- Same-origin API and WebSocket behavior preserved for AWS deployment.

### Changed
- Frontend version synchronized to 2.2.0-rc.1.
- Critical frontend dependencies changed to exact versions for reproducible builds.
- Existing market dashboard retained without changing trading logic.

### Safety
- Live Zerodha order placement remains disabled.
- Protected paper actions continue to require X-Admin-Token.

## [2.2.0-rc.2] - 2026-08-03
- Completed paper portfolio, journal, timeline and manual-close workflow.
- Added pre-trade Risk Supervisor and emergency kill switch.
- Added risk dashboard and portfolio APIs.
- Added migration 005_risk_supervisor.sql and regression tests.

## [2.2.0-rc.3] - 2026-08-03

### Added
- Paper analytics API with equity curve, drawdown, expectancy and profit factor.
- CE/PE, grade and exit-reason breakdowns.
- Decision replay APIs with setup snapshot and monitor timeline.
- Analytics and Replay dashboard pages.

### Compatibility
- Existing paper trading, risk, Zerodha data and deployment interfaces are unchanged.
- Automatic Zerodha order execution remains disabled.

## [2.3.0-rc.1] - 2026-08-03
- Added read-only Operations Console APIs and UI.
- Added multi-agent registry and decision-bus workspace.
- Added conservative Strategy Lab validation API and UI.
- Added tests for operations resources and Strategy Lab safeguards.
- Live Zerodha execution remains disabled.

## 2.4.0-rc.1
- Added Zerodha live-data freshness/status controls.
- Added manual execution preview, idempotency and explicit confirmation queue.
- Added production security headers and HTTPS/live-order safety switches.
- Added Production workspace.

## 2.5.0-rc.1
- Added restart-safe market-data supervisor with persisted feed state.
- Added token/session health, polling recovery metrics and safe NO_TRADE fallback.
- Added NFO instrument-master synchronization endpoint and status.
- Added 3-minute spot candle aggregation from verified market snapshots.
- Added live-data poll, instrument sync and candle APIs.
- Expanded Production workspace with feed quality and candle visibility.
- Kept live Zerodha order placement disabled.

## 2.6.0-rc.1
- Added option-chain intelligence APIs and institutional bias scoring.
- Added PCR, OI-change, max-pain, call-wall and put-wall analytics.
- Added V2.6 option-chain intelligence panel to the Production workspace.
- Preserved V2.5 live-data safety controls and disabled automatic broker execution.

## 2.7.0-rc.1
- Added institutional-flow intelligence, buildup classification, PCR trend, data-quality warnings, APIs and dashboard page.

## 2.7.0-rc.2
- Persisted intraday institutional-flow and PCR snapshots.
- Added flow trend, anomaly, and decision-intelligence APIs.
- Added institutional-flow evidence to paper-trade replay.
- Added intraday trend and anomaly panels to the Institutional Flow workspace.

## 2.8.0-rc.1
- Added AI Supervisor v2 with weighted scoring, agent voting, confidence and A/A+ recommendation filter.
- Added market regime, smart-money structure and Greeks-based gamma intelligence.
- Added AI Command Center API and dashboard workspace.
- Added V2.8 regression tests; full backend suite now passes 61 tests.

## 6.8.0-rc.1
- Added configurable multi-session live-data certification.
- Added certification notification report API and Live Intelligence panel.
- Added cross-session readiness, WebSocket, error, and feed-age thresholds.
## 7.5.3
- Added optional read-only Upstox V3 Full Market Quote adapter for independent NIFTY 50 evidence.
- Added provider-native instrument identity to MarketDataEnvelope V2.
- Added multi-session shadow-consensus certification with explicit promotion blockers.
- Preserved shadow-only defaults, disabled live orders, and made no AWS deployment changes.
