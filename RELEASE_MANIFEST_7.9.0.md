# V7.9.0 release manifest

Base: checksum-verified V7.8.4 audit candidate (`d5d0f939ee5a11880aa5e8a65407ac2b9a37e602afc6d2cdbf11838f060db437`).

New production modules: `paper_decision_orchestrator.py`, `paper_costs.py`. Modified safety-critical modules: pipeline, automatic paper worker, paper bridge, lifecycle management, journal, configuration and readiness. Modified UI: autonomous paper operator page, API types and header. New tests: `test_v790_costs_orchestrator.py` plus finalized-pipeline and readiness cases.

The ZIP excludes virtual environments, `node_modules`, Python/test caches, local environment files, runtime databases/state/logs and backup source copies. Frontend compiled assets are included. No Git push or AWS deployment was performed.

AWS entry points: `scripts/deploy_v790_aws.sh` performs guarded install/test/switch/rollback; `scripts/verify_v790_aws.sh` performs read-only post-deployment verification.

Known blocker: Zerodha Kite Connect 5.2.2 transitively pins vulnerable Autobahn 19.11.2. V7.9 readiness therefore requires `KITE_WEBSOCKET_REQUESTED=false`.
