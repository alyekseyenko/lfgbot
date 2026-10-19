# Runbook operacional — LFG Valorant

Referência rápida para incidentes. SLOs detalhados em [SLO.md](SLO.md). Alertas em `deploy/observability/prometheus/alerts.yml`.

## Health

| Endpoint | Significado |
|----------|-------------|
| `GET /health/live` | Processo responde |
| `GET /health/ready` | Postgres OK + `bot.is_ready()` + gateway |

**Falha ready:** ver logs do container `app`; testar `SELECT 1` na BD; confirmar `DISCORD_TOKEN` e intents no portal.

## Bot caiu, BD OK

1. Estado de lobbies está em Postgres — **não se perde** ao reiniciar.
2. `docker compose restart app` (ou stack VPS equivalente).
3. No arranque, procurar log: `reconciled N active lobbies on startup`.
4. Job periódico (`RECONCILE_POLL_SECONDS`) refresca embeds de lobbies `open`/`full` a partir da BD.

## Discord HTTP 429 (rate limit)

- Sintoma: `lfg_discord_http_errors_total`, embeds atrasados.
- Ação: não reduzir `EMBED_DEBOUNCE_SECONDS` sem necessidade; esperar; evitar scripts que editam muitas mensagens de uma vez.
- Métrica útil: `lfg_embed_edits_total` vs `lfg_embed_events_total` (debounce a funcionar).

## Config do dashboard não reflete no bot

- Settings vêm de `guild_settings` com cache TTL ([ADR 006](adr/006-multi-guild-config-cache.md)).
- PATCH na API invalida cache; se suspeita de cache velho, reiniciar `app` (último recurso).
- Confirmar guild correcta no admin e `bot_installed=true`.

## Expiração de lobbies

- Job `expiration_loop` corre a cada `EXPIRE_POLL_SECONDS` (default 30).
- `expires_at` definido na publicação (TTL da guild).
- Lobbies expirados: embed em modo `EXPIRED_MODE` (edit/delete).

## Rollback de deploy

**VPS test (`docker-compose.vps-test.yml`):**

```bash
cd $VPS_LFG_DIR
git log -1 --oneline
git checkout <commit-anterior>   # ou git pull se o remoto já tem o fix
docker compose -f docker-compose.vps-test.yml build app
docker compose -f docker-compose.vps-test.yml up -d
curl -s http://127.0.0.1:8010/health/ready
```

Mantém `.env` no servidor; não commitar segredos ([SECURITY.md](SECURITY.md)).

## Um token, uma instância

Parar `app` local antes de subir no VPS. Dois processos com o mesmo token desconectam-se mutuamente.

## Observabilidade

```bash
docker compose --profile observability up -d
```

- Prometheus: `:9090`
- Grafana: `:3000` (dashboard `LFG Valorant`)

## Backup Postgres

Ver `scripts/backup.sh` e política do host. Testar restore em ambiente de teste antes de depender em produção.
