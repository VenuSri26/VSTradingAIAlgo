# Release manifest — 7.8.4-audit-rc1

This release was produced from the supplied `VSTradingAI-v7.8.3-audit-checkpoint1.zip`. The source archive contained no `.git` directory, so no improvement branch or Git bundle could be truthfully created. The deliverable is a clean ZIP.

Included: application source, migrations, test suite, frontend production build, configuration template, audit report, test report, research register, change register, deployment/rollback guide.

Excluded: audit virtual environment, npm cache/modules, Python caches, pytest cache, runtime SQLite databases, runtime JSON/JSONL state, obsolete source backup copies, credentials and local environment files. Quarantined originals remain outside the deliverable in the audit workspace.

Changed behavior:

- completed aligned 3-minute candle required for automatic evaluation;
- durable cycle idempotency uses candle start;
- managed holiday calendar participates in the paper loop and corruption fails closed;
- strike selection requires bid/ask freshness, spread, OI and volume thresholds;
- paper entry uses ask-side reference and records slippage;
- journal includes strategy version, input snapshot evidence, MFE and MAE;
- direct dependencies updated and release version advanced.

Rollback is by atomic release symlink switch; see `DEPLOYMENT_7.8.4.md`.
