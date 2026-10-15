#!/bin/sh
# Backup PostgreSQL (correr no VPS via cron). Destino opcional: BACKUP_DEST (ex. user@host:/backups/)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE="docker compose -f docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-$ROOT/backups}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/lfg-$STAMP.sql.gz"

mkdir -p "$BACKUP_DIR"

$COMPOSE exec -T postgres pg_dump -U "${POSTGRES_USER:-lfg}" "${POSTGRES_DB:-lfg}" | gzip -9 >"$FILE"

find "$BACKUP_DIR" -name 'lfg-*.sql.gz' -mtime +"$KEEP_DAYS" -delete 2>/dev/null || true

if [ -n "${BACKUP_DEST:-}" ]; then
  scp -q "$FILE" "$BACKUP_DEST" || echo "backup: falha ao enviar para BACKUP_DEST" >&2
fi

echo "backup: $FILE"
