# Deploy on Hetzner (24/7)

One **Discord bot token** → only **one** online instance (local **or** VPS).

## 1. Server

- Ubuntu LTS VPS (e.g. CPX22+), SSH key auth.
- Firewall: **22**, **80**, **443** (if using Caddy from `docker-compose.prod.yml`).

## 2. Docker

```bash
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
# Install Docker Engine + compose plugin (see https://docs.docker.com/engine/install/ubuntu/)
sudo usermod -aG docker "$USER"
```

## 3. Clone and `.env`

```bash
git clone https://github.com/alyekseyenko/lfgbot.git lfg
cd lfg
cp .env.example .env
nano .env
```

Set at minimum:

- `DISCORD_TOKEN`, `DISCORD_APPLICATION_ID`, `DISCORD_GUILD_IDS`, `LFG_CHANNEL_IDS`
- `POSTGRES_PASSWORD` (strong; VPS only)
- `DATABASE_URL` is overridden by compose for host `postgres`

Enable **Message Content Intent** in the Developer Portal if `AUTO_FORMAT_MESSAGES=true`.

## 4. Start

```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
docker compose -f docker-compose.prod.yml logs -f app
```

Expect: `discord bot logged in as ...`

## 5. Stop local bot

```powershell
docker compose stop app
```

## 6. Updates

```bash
cd ~/lfg && ./scripts/deploy.sh
```

## Shared host with existing nginx

Do **not** bind Caddy to 80/443 on that machine. Use [DEPLOY_VPS_TEST.md](DEPLOY_VPS_TEST.md) instead.
