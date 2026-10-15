#!/bin/sh
# Deploy no VPS: pull, build, migrações, restart.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f docker-compose.prod.yml"

git pull --ff-only

$COMPOSE build app
$COMPOSE up -d

echo "deploy: containers a correr. Verifica: $COMPOSE logs -f app --tail 30"
