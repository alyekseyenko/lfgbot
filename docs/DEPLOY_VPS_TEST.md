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

## Admin dashboard

The API serves the built SPA from `frontend/dist` (see `SPA_STATIC_DIR` in compose). After deploy, build once on the VPS (`npm ci && npm run build` in `frontend/`) or upload `frontend/dist` from your PC.

### A) SSH tunnel (no public URL)

On your PC:

```bash
ssh -L 8010:127.0.0.1:8010 root@YOUR_VPS_HOST
```

Open **http://localhost:8010/admin** (same tab; API + UI on port 8010).

In the VPS `.env` (for OAuth to work over the tunnel):

```env
PUBLIC_APP_URL=http://localhost:8010
OAUTH_REDIRECT_URI=http://localhost:8010/auth/discord/callback
```

Add the same redirect URL in the [Discord Developer Portal](https://discord.com/developers/applications) → OAuth2 → Redirects. Restart the app after changing `.env`.

### B) Nginx + HTTPS (production)

Point a subdomain (e.g. `lfg.example.com`) to the VPS, proxy to `127.0.0.1:8010`, set `PUBLIC_APP_URL` and `OAUTH_REDIRECT_URI` to `https://lfg.example.com/...`, and register that redirect in Discord.

Without OAuth you can still use Discord slash commands (`/lfg-painel`, `/lfg-guia`, `/lfg-stats`).

## Updates

```bash
cd ~/lfg-test && git pull --ff-only
docker compose -f docker-compose.vps-test.yml build app
docker compose -f docker-compose.vps-test.yml up -d
```
