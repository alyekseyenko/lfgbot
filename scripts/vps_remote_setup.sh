#!/bin/sh
# Run ON the VPS inside the repo directory after .env is configured.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose -f docker-compose.vps-test.yml"
if [ ! -f .env ]; then
  echo "Missing .env — copy .env.example and set DISCORD_TOKEN, POSTGRES_PASSWORD, guild/channel IDs."
  exit 1
fi
if command -v npm >/dev/null 2>&1; then
  echo "Building admin SPA (frontend/dist)..."
  (cd frontend && npm ci && npm run build)
else
  echo "WARN: npm not found — admin UI needs frontend/dist (install Node 20+ or build locally and rsync dist/)."
fi
$COMPOSE build app
$COMPOSE up -d
echo "Logs: $COMPOSE logs -f app --tail 40"
echo "Health: curl -s http://127.0.0.1:8010/health/ready"
