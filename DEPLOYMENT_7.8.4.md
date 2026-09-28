# AWS Lightsail deployment and rollback — 7.8.4 audit candidate

This candidate is **paper-only**. Do not enable WebSocket or live orders while the dependency/security and readiness blockers in the audit remain open.

## Placeholders

- `<ARCHIVE>`: uploaded release ZIP path; not a password or token.
- `<SHA256>`: checksum published with the archive.
- `<ZERODHA_API_KEY>`: Kite Connect application's public API key.
- `<ZERODHA_API_SECRET>`: Kite Connect application secret; never a GitHub token.
- `<ZERODHA_REQUEST_TOKEN>`: short-lived token returned by Zerodha's login redirect; exchange it once for an access token.
- `<ZERODHA_ACCESS_TOKEN>`: daily broker session token returned by Kite; never a GitHub PAT.
- `<ADMIN_TOKEN>`: strong private token protecting administrative HTTP routes.
- `<GITHUB_PAT>`: used only for GitHub HTTPS authentication if needed; it is never valid for Zerodha.

## Backup, stage and validate

```bash
set -euo pipefail
sha256sum <ARCHIVE>
# Compare output manually with <SHA256> before continuing.
sudo install -d -o ubuntu -g ubuntu /opt/vstradingai/releases
RELEASE=/opt/vstradingai/releases/v7.8.4-audit-rc1
mkdir -p "$RELEASE"
unzip -q <ARCHIVE> -d "$RELEASE"
sudo cp -a /opt/vstradingai/shared/backend.env "/opt/vstradingai/backups/backend.env.$(date -u +%Y%m%dT%H%M%SZ)"
```

The shared environment must include:

```dotenv
TRADING_MODE=mock
LIVE_ORDERS_ENABLED=false
PAPER_AUTO_TRADER_ENABLED=false
KITE_WEBSOCKET_REQUESTED=false
ZERODHA_API_KEY=<ZERODHA_API_KEY>
ZERODHA_API_SECRET=<ZERODHA_API_SECRET>
ADMIN_TOKEN=<ADMIN_TOKEN>
```

Never paste `<GITHUB_PAT>` into the Zerodha refresh utility. The refresh utility expects the Zerodha **request token from the login redirect**, not an API secret, access token or GitHub token.

```bash
cd "$RELEASE/VSTradingAI-v7.8.4-audit-rc1/backend"
python3 -m venv .venv
.venv/bin/pip install --requirement requirements.lock
PYTHONPATH=. .venv/bin/pytest -q tests
cd ../frontend
npm ci
npm run build
```

## Switch and health validation

```bash
OLD_RELEASE=$(readlink -f /opt/vstradingai/current || true)
sudo ln -sfn "$RELEASE/VSTradingAI-v7.8.4-audit-rc1" /opt/vstradingai/current.next
sudo mv -Tf /opt/vstradingai/current.next /opt/vstradingai/current
sudo systemctl restart vstradingai-api.service
sudo systemctl is-active vstradingai-api.service
curl -fsS --max-time 20 http://127.0.0.1:8000/healthz
test "$(grep -E '^LIVE_ORDERS_ENABLED=' /opt/vstradingai/shared/backend.env)" = 'LIVE_ORDERS_ENABLED=false'
```

Confirm health says `PAPER_ONLY` and `live_orders_enabled:false`. Keep `PAPER_AUTO_TRADER_ENABLED=false` until a supervised session passes.

## Rollback

```bash
test -n "$OLD_RELEASE" && test -d "$OLD_RELEASE"
sudo ln -sfn "$OLD_RELEASE" /opt/vstradingai/current.rollback
sudo mv -Tf /opt/vstradingai/current.rollback /opt/vstradingai/current
sudo systemctl restart vstradingai-api.service
sudo systemctl is-active vstradingai-api.service
curl -fsS --max-time 20 http://127.0.0.1:8000/healthz
```

Rollback does not delete the failed release. Preserve logs and its database copy for diagnosis. Never copy a newer database backward until migration compatibility is confirmed.
