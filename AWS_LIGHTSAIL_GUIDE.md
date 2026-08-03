# AWS Lightsail Installation and Testing

## Recommended instance
Ubuntu 24.04 LTS, at least 2 GB RAM for backend and dashboard development. Open ports 22, 80 and 443 in Lightsail networking. Do not expose port 8000 publicly.

## Install

```bash
unzip vstradingai_zerodha_safe.zip
cd vstradingai_zerodha_safe
sudo ./install_aws_lightsail.sh
```

The installer creates `/opt/vstradingai`, a Python virtual environment, a systemd service and an Nginx reverse proxy.

## Configure

```bash
sudo nano /opt/vstradingai/backend/.env
```

Start with `TRADING_MODE=mock`. For Zerodha live market data, fill `KITE_API_KEY`, `KITE_API_SECRET`, the daily `KITE_ACCESS_TOKEN`, and a strong `ADMIN_TOKEN`. Automatic order placement remains disabled.

```bash
sudo systemctl restart vstradingai-api
sudo journalctl -u vstradingai-api -n 100 --no-pager
```

## Validate

```bash
sudo /opt/vstradingai/test_aws_lightsail.sh
curl http://localhost/healthz
curl http://localhost/api/decision/live
```

## Daily Zerodha token update

```bash
sudo nano /opt/vstradingai/backend/.env
sudo systemctl restart vstradingai-api
sudo /opt/vstradingai/test_aws_lightsail.sh
```

## Security

Keep `.env` permissions at `600`. Use HTTPS before remote access. Position-changing endpoints require the `X-Admin-Token` header when an admin token is configured. Never commit Zerodha credentials or access tokens to GitHub.

## Version 1.1 deployment safety

The installer automatically creates a `pre-deploy` backup when an older installation already exists. Backups are stored under `/opt/vstradingai-backups` with root-only permissions.

After installation, validate the release:

```bash
sudo /opt/vstradingai/test_aws_lightsail.sh
```

The command creates a signed validation report under:

```text
/opt/vstradingai/deployment/validation/
```

Check the running version:

```bash
curl http://127.0.0.1:8000/api/system/version
```

Rollback procedure:

```bash
sudo /opt/vstradingai/rollback_aws_lightsail.sh --list
sudo /opt/vstradingai/rollback_aws_lightsail.sh <selected-backup>
```

Rollback first creates an additional safety backup, verifies the selected archive checksum, restarts the service, and automatically reinstates the previous application if the restored health check fails.

## Verify Version 1.3.0 features

```bash
curl http://127.0.0.1:8000/api/system/version
curl http://127.0.0.1:8000/api/system/zerodha-health
curl http://127.0.0.1:8000/api/setups
```

In live mode, the Zerodha health endpoint should report `connected: true` after a valid daily access token is configured. It never returns the API secret or access token.

## Version 1.4.0 paper-engine validation

After deployment, confirm:

```bash
curl http://127.0.0.1:8000/api/system/version
curl http://127.0.0.1:8000/api/paper/trades
```

Configure `PAPER_CAPITAL`, `MAX_RISK_PER_TRADE_PCT`, `PAPER_SLIPPAGE_RUPEES`, and `PAPER_COST_RATE` in `/opt/vstradingai/backend/.env`, then restart the service. Paper execution requires `X-Admin-Token`. No endpoint in this release sends a Zerodha order.

## Run strategy validation on AWS (v1.5.0)
Upload chronological candle and signal CSV files, then run:

```bash
cd /opt/vstradingai/backend
source .venv/bin/activate
python scripts_validate_strategy.py /path/candles.csv /path/signals.csv > validation-output.json
```

This process is offline and does not submit Zerodha orders or change live strategy settings.


## Version 1.6.0 checks
After deployment, confirm `/api/decision/live` contains `alignment.coverage_ratio`, `alignment.disagreement_score`, `alignment.calibrated_confidence`, and `debate`. Recommended defaults are `MIN_AGENT_COVERAGE=0.70` and `MAX_AGENT_DISAGREEMENT=0.45`.


## Version 1.7 operational monitoring

Check services and timers:

```bash
systemctl status vstradingai-api
systemctl status vstradingai-health-report.timer
systemctl status vstradingai-backup.timer
systemctl list-timers 'vstradingai-*'
```

Run an immediate operations check and health report:

```bash
sudo /opt/vstradingai/operations_check.sh
sudo /opt/vstradingai/daily_health_report.sh
```

Review JSON logs and recent alerts:

```bash
tail -f /opt/vstradingai/backend/data/vstradingai.jsonl
curl http://127.0.0.1:8000/api/system/alerts?limit=20
```

## Version 2.0 staged deployment
```bash
sudo ./preflight_aws_lightsail.sh
sudo ./install_aws_lightsail.sh
sudo /opt/vstradingai/current/test_aws_lightsail.sh
```
Configuration is retained at `/opt/vstradingai/shared/backend.env`. Runtime data is retained at `/opt/vstradingai/shared/data`. Releases are immutable directories under `/opt/vstradingai/releases`.

After adding a valid daily token, execute only the read-only broker validation:
```bash
sudo APP_DIR=/opt/vstradingai/current /opt/vstradingai/current/validate_zerodha_readonly.sh
```
