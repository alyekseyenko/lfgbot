# LFG Valorant (Discord)

![CI](https://github.com/alyekseyenko/lfgbot/actions/workflows/ci.yml/badge.svg)

Open-source Discord bot for **looking-for-group (LFG)** in a Portuguese Valorant community (~13k members). It turns the old habit of posting `CODE +2 @RANK` in chat into a **structured request** with embeds, buttons, and state stored in PostgreSQL.

Repository: **https://github.com/alyekseyenko/lfgbot**

Architecture and roadmap (Portuguese): [docs/PROJETO.md](docs/PROJETO.md). English deploy guides: [docs/DEPLOY_HETZNER.md](docs/DEPLOY_HETZNER.md), [docs/DEPLOY_VPS_TEST.md](docs/DEPLOY_VPS_TEST.md).

**User-facing bot text is European Portuguese** (community language). This README and ops docs are in English.

---

## Before and after

| Before (manual chat) | After (LFG bot) |
|----------------------|-----------------|
| Stacked `ZOV825 +2 @GOLD` messages | Embed with slots, ranks, party code, **Join** / **Leave** buttons |
| No shared state | PostgreSQL is source of truth; Discord is the UI |
| Stale requests mixed with active ones | **Open** / **Full** / **Closed** / **Expired** with auto-expiry |

Screenshots: [docs/images/](docs/images/).

---

## Features

- **`/procurar`** — create LFG (slots, party code, rank range, agents, public/private code).
- **Auto-format** — `ABC123 +2 @PLATINUM` style messages become embeds (needs **Message Content Intent**).
- **«Criar grupo» panel** — sticky message + button (`/lfg-painel` for staff).
- **Persistent buttons** — survive bot restarts.
- **`/fechar`**, **`/editar`**, **`/lfg-stats`**, **`/lfg-apagar-dados`** (GDPR).
- Optional **gamification** — `/perfil`, `/ranking`, LFG roles.
- **Web admin** — multi-guild settings, embed themes, Valorant catalog sync (`frontend/` + OAuth).

---

## Stack

| Layer | Tech |
|--------|------|
| Bot + API | Python 3.12, discord.py, FastAPI (monolith) |
| Data | PostgreSQL, SQLAlchemy 2 async, Alembic |
| Admin UI | React, Vite, TypeScript |
| Deploy | Docker Compose |
| Tests | pytest, mypy, ruff |

---

## Quick start (local)

```bash
cp .env.example .env
# Fill DISCORD_TOKEN, DISCORD_GUILD_IDS, LFG_CHANNEL_IDS
docker compose up --build
```

- Dashboard (dev): http://localhost:5190  
- API: http://localhost:8000  

Migrations run on `app` startup. Confirm **ready** in logs.

Windows: `.\scripts\docker-dev.ps1`

---

## Tests

```bash
docker compose exec app pytest -q
```

---

## Deploy 24/7

- Dedicated VPS: [docs/DEPLOY_HETZNER.md](docs/DEPLOY_HETZNER.md) (`docker-compose.prod.yml`).
- **Shared VPS** (nginx already on 80/443): [docs/DEPLOY_VPS_TEST.md](docs/DEPLOY_VPS_TEST.md) (`docker-compose.vps-test.yml`, API on `127.0.0.1:8010`).

**One Discord token = one running instance.** Stop local `app` before starting on the VPS.

---

## License

See [LICENSE](LICENSE).
