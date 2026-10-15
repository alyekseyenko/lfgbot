# Test deploy on a shared VPS (nginx + other Docker stacks)

Use this when **ports 80/443 and 8000 are already taken** (e.g. existing nginx reverse proxy).

## Stack

- `docker-compose.vps-test.yml` — **Postgres + app only** (bot + API monolith).
- API bound to **`127.0.0.1:8010`** (does not conflict with other services on `:8000`).
- No Caddy container (your host nginx handles public HTTP/S).

## Steps on the server

```bash
cd ~
git clone https://github.com/alyekseyenko/lfgbot.git lfg-test
cd lfg-test
cp .env.example .env
nano .env   # DISCORD_TOKEN, DISCORD_GUILD_IDS, LFG_CHANNEL_IDS, strong POSTGRES_PASSWORD
docker compose -f docker-compose.vps-test.yml up -d --build
docker compose -f docker-compose.vps-test.yml logs -f app --tail 50
```

Look for: `discord bot logged in as ...`

Health (on the VPS): `curl -s http://127.0.0.1:8010/health/ready`

## One bot instance

Stop the bot on your PC before starting on the VPS (`docker compose stop app`). The same Discord token cannot run twice.

## Admin dashboard (optional, private)

For OAuth you need **HTTPS + a domain** in the Discord Developer Portal (`OAUTH_REDIRECT_URI`, `PUBLIC_APP_URL`). Raw IP-only admin login is unreliable.

For a quick API test without the web UI, configure guild channels via `.env` and use Discord commands; use the dashboard later behind nginx + subdomain.

## Updates

```bash
cd ~/lfg-test && git pull --ff-only
docker compose -f docker-compose.vps-test.yml build app
docker compose -f docker-compose.vps-test.yml up -d
```
