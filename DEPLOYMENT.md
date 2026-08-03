# Deploying VSTradingAI to AWS Lightsail

Step-by-step for a fresh Lightsail instance. Written for Ubuntu 22.04/24.04.

## 0. Create the Lightsail instance (if you haven't already)

1. AWS Console → Lightsail → Create instance
2. Platform: **Linux/Unix** → Blueprint: **OS Only → Ubuntu 22.04 LTS**
3. Plan: 1 GB RAM / 2 vCPU is enough to run this backend + frontend build
4. Create the instance, download/note the SSH key if not using browser SSH
5. Under the instance's **Networking** tab, add firewall rules:
   - TCP 22 (SSH) — usually already open
   - TCP 8000 (backend API/WebSocket) — for testing directly; lock this down or put behind Nginx once verified
   - TCP 80/443 (if you'll serve the frontend build via Nginx)
6. Note the instance's **public IP** — you'll need it below.

## 1. Transfer the zip to the server

From your local machine, in the folder containing `vstradingai.zip`:

```bash
scp -i /path/to/your-lightsail-key.pem vstradingai.zip ubuntu@<PUBLIC_IP>:~
```

(If you downloaded the key from Lightsail's browser SSH, use that `.pem`
file. Default Lightsail Ubuntu user is `ubuntu`.)

## 2. SSH in and unpack

```bash
ssh -i /path/to/your-lightsail-key.pem ubuntu@<PUBLIC_IP>
unzip vstradingai.zip -d vstradingai
cd vstradingai
```

## 3. Install system prerequisites

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv nodejs npm sqlite3 unzip curl

# Confirm versions (need Python 3.10+, Node 18+)
python3 --version
node --version
```

If Ubuntu's default `nodejs` is too old (`node --version` < 18), install a
current one instead:
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

## 4. Backend setup

```bash
cd ~/vstradingai/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
nano .env    # set TRADING_MODE=mock to start, or live + Kite credentials

# validate config before starting anything
PYTHONPATH=. python -m app.config
```

Run the backend test suite (all 50 checks across pipeline/store/position/backtest):
```bash
PYTHONPATH=. pytest -v
# or, without pytest:
for f in tests/test_pipeline.py tests/test_store.py tests/test_position_info.py tests/test_backtest.py; do
  python3 "$f"
done
```

Start the backend (quick foreground test first):
```bash
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Ctrl+C once you've confirmed it starts cleanly, then run it properly via
`start_nifty.sh` or systemd (below).

Test from your local machine:
```bash
curl http://<PUBLIC_IP>:8000/healthz
curl http://<PUBLIC_IP>:8000/api/decision/live | python3 -m json.tool
```

## 5. Keep the backend running (systemd service)

Create `/etc/systemd/system/vstradingai.service`:
```ini
[Unit]
Description=VSTradingAI backend
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/vstradingai/backend
Environment="PYTHONPATH=/home/ubuntu/vstradingai/backend"
ExecStart=/home/ubuntu/vstradingai/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable vstradingai
sudo systemctl start vstradingai
sudo systemctl status vstradingai       # confirm it's active (running)
journalctl -u vstradingai -f            # tail logs
```

This also gives you the daily-restart hook you'll want for the Zerodha
token refresh: `sudo systemctl restart vstradingai` after updating
`KITE_ACCESS_TOKEN` in `.env` each morning (or wire that into `start_nifty.sh`
via a cron job, see step 8).

## 6. Frontend setup

```bash
cd ~/vstradingai/frontend
npm install
echo "VITE_API_BASE_URL=http://<PUBLIC_IP>:8000" > .env
npm run build       # produces frontend/dist/
```

Serve the build with Nginx (recommended for a real deployment):
```bash
sudo apt install -y nginx
sudo tee /etc/nginx/sites-available/vstradingai <<'EOF'
server {
    listen 80;
    root /home/ubuntu/vstradingai/frontend/dist;
    index index.html;
    location / { try_files $uri /index.html; }
}
EOF
sudo ln -s /etc/nginx/sites-available/vstradingai /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx
```

Now the dashboard is at `http://<PUBLIC_IP>/` and it talks to the backend
at `http://<PUBLIC_IP>:8000`.

For a quick local-only check instead of Nginx: `npm run preview` and open
the URL it prints (from the same server, or via SSH port forwarding:
`ssh -L 5173:localhost:5173 -i key.pem ubuntu@<PUBLIC_IP>`).

## 7. Going live with real Zerodha data

```bash
cd ~/vstradingai/backend
source venv/bin/activate
# kiteconnect is already in requirements.txt, but confirm:
pip show kiteconnect
```
In `.env`: set `TRADING_MODE=live`, `KITE_API_KEY`, `KITE_API_SECRET`, and a
freshly generated `KITE_ACCESS_TOKEN` (regenerate daily — it expires every
day; this is exactly the failure mode `app/config.py` and `start_nifty.sh`
guard against). Then:
```bash
sudo systemctl restart vstradingai
curl http://localhost:8000/api/system/config-check
```
`ok: true` means it validated; `ok: false` lists exactly what's missing.

## 8. Daily morning routine (once live)

```bash
cd ~/vstradingai
nano backend/.env      # paste today's fresh KITE_ACCESS_TOKEN
./start_nifty.sh        # validates + restarts + health-checks everything
```
You can cron the token-refresh reminder, but the actual token value has to
come from your Kite login flow each day — that step can't be automated
without storing long-lived credentials, which Kite's daily-expiry design
specifically prevents.

## 9. Final checklist before trusting it with real capital

- [ ] `pytest -v` passes (or the 4 manual test scripts all report 0 failed)
- [ ] `/api/system/config-check` returns `ok: true` in live mode
- [ ] `/api/decision/live` returns real data with `source: "ZERODHA"` in
      `market`, not `"MOCK"`
- [ ] `/healthz` and Nginx-served dashboard both reachable from your browser
- [ ] Firewall: port 8000 restricted to your IP (or behind Nginx auth) —
      don't leave a trading API open to the whole internet
- [ ] `systemctl status vstradingai` shows `Restart=always` is active, so a
      crash doesn't silently take the system offline mid-session
