# V7.9.0 safe deployment outline

Deploy this release with automation initially disarmed:

```dotenv
TRADING_MODE=live
LIVE_ORDERS_ENABLED=false
PAPER_AUTO_TRADER_ENABLED=false
PAPER_REQUIRE_FULL_PIPELINE=true
KITE_WEBSOCKET_REQUESTED=false
```

`TRADING_MODE=live` here selects authenticated live **data**. It does not authorize orders; `LIVE_ORDERS_ENABLED=false` is mandatory.

`<ZERODHA_REQUEST_TOKEN>` means the short-lived request token returned by the Kite login redirect. It is not a GitHub token, API secret or existing access token. `<GITHUB_PAT>` is only for GitHub HTTPS authentication.

```bash
set -euo pipefail
sha256sum <V7_9_ZIP>
RELEASE=/opt/vstradingai/releases/v7.9.0-paper-rc1
mkdir -p "$RELEASE"
unzip -q <V7_9_ZIP> -d "$RELEASE"
cd "$RELEASE/VSTradingAI-v7.9.0-paper-rc1/backend"
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
PYTHONPATH=. .venv/bin/pytest -q tests
cd ../frontend && npm ci && npm run build
```

Back up `/opt/vstradingai/shared/backend.env` and the SQLite database before switching the symlink. Apply migrations through the existing startup migration runner. Atomically switch `/opt/vstradingai/current`, restart `vstradingai-api.service`, then verify `/healthz`, `/api/paper/readiness`, Zerodha health and `LIVE_ORDERS_ENABLED=false`.

Rollback by atomically repointing `/opt/vstradingai/current` to the previous release and restarting the service. Do not downgrade the database file without restoring its matching pre-deployment backup.
