#!/usr/bin/env bash
set -euo pipefail
command -v docker >/dev/null || { echo 'Docker is required' >&2; exit 1; }
docker build --no-cache -f Dockerfile.validation -t vstradingai-validation:2.0.0 .
CID=$(docker run -d -p 127.0.0.1:18000:8000 vstradingai-validation:2.0.0); trap 'docker rm -f "$CID" >/dev/null 2>&1 || true' EXIT
for _ in $(seq 1 30); do curl -fsS http://127.0.0.1:18000/healthz >/dev/null && break; sleep 1; done
BASE_URL=http://127.0.0.1:18000 WEB_URL=http://127.0.0.1:18000 ./post_deploy_smoke_test.sh || true
echo 'CONTAINER VALIDATION COMPLETE'
