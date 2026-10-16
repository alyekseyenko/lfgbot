# LFG Valorant (Discord)

![CI](https://github.com/alyekseyenko/lfgbot/actions/workflows/ci.yml/badge.svg)

Open-source Discord bot for **looking-for-group (LFG)** in a Portuguese Valorant community. It replaces years of manual `CODE +2` chat posts with **structured requests** (embeds, buttons, PostgreSQL as source of truth).

Repository: **https://github.com/alyekseyenko/lfgbot**

Architecture and roadmap (Portuguese): [docs/PROJETO.md](docs/PROJETO.md). English deploy guides: [docs/DEPLOY_HETZNER.md](docs/DEPLOY_HETZNER.md), [docs/DEPLOY_VPS_TEST.md](docs/DEPLOY_VPS_TEST.md).

**User-facing bot text is European Portuguese** (community language). This README and ops docs are in English.

---

## Community scale (since 2023)

The server has used dedicated LFG channels since **2023** (~3–4 years of daily manual posts before this bot). Today the Discord has on the order of **~13,000 members**.

Production metrics combine **historical channel activity** (configured once in guild settings) with **live data** recorded by the bot after rollout:

| Metric | Lifetime total (approx.) | Meaning |
|--------|-------------------------|---------|
| **Group requests** | **384,931+** | Times someone looked for a team (legacy channel posts + bot `lobbies` since deploy). |
| **Joins** | **1,154,793+** | Times players joined a request (**Entrar** / lobby members); legacy estimate ≈ 3× requests. |
| **Players** | **8,200+** | Distinct people who used LFG (legacy estimate + Discord IDs stored by the bot). |

The `+` counts **bot-tracked** activity on top of the legacy baseline. Staff can tune baselines in the web admin (**Histórico antes do bot**); `/lfg-stats` and the dashboard show **period** stats (e.g. last 30 days) separately.

| | |
|--|--|
| **Bot in production** | 2025–2026 (Docker on VPS; monolith bot + API + admin). |
| **Open source** | This repository — self-host or adapt for your guild. |

---

## Before and after

| Before (manual chat) | After (LFG bot) |
|----------------------|-----------------|
| Stacked `ZOV825 +2 @GOLD` messages | Structured embeds: party code, slots, ranks, host |
| No shared state | PostgreSQL is source of truth; Discord is the UI |
| Stale requests mixed with active ones | **Open** / **Full** / **Closed** / **Expired** with auto-expiry |

**Post styles:** **Simple** (default) — code in-channel, join in-game, host-only **Close** button. **Detailed** — **Join** / **Leave** list on Discord (legacy flow).

Screenshots: [docs/images/](docs/images/).

---

## Features

### Creating requests

- **`/procurar`** — defaults to **simple** (`slots` + `party code`). Use `type: Detailed` for Join/Leave on Discord (rank range, agents, public/private code, verified ranks).
- **«Criar grupo» panel** — **Simple** (recommended) or **Detailed**; sticky message + button (`/lfg-painel` to republish).
- **Guide channel** — short PT embed for members (editable in admin → General; `/lfg-guia` to publish).

### Simple vs detailed embeds

| | **Simple** | **Detailed** |
|--|------------|--------------|
| Discord buttons | Host **Close** only | **Join** / **Leave** (+ host tools) |
| Party code | Shown in the channel embed | Public in embed or **DM after Join** if private |
| Ranks | Optional min/max on the embed (informational) | Enforced via mapped Discord rank roles |
| VIP / priority roles | Highlight styling (title/color/thumbnail) when enabled | Same tier styling when enabled |
| Host in embed | Display name (not a broken `@mention` in embed body) | Same |
| Footer accent | Mapped Valorant rank role icon, or “unverified rank” copy | Full member list + standard footer rules |

### Ops and community

- **Auto-format** (optional) — `ABC123 +2` chat → embeds; many guilds use panel/slash only.
- **Persistent views** — buttons survive bot restarts (`custom_id`).
- **Commands** — `/fechar`, `/editar`, `/perfil`, `/ranking`, `/lfg-stats`, `/lfg-apagar-dados` (GDPR).
- **Moderation** — leave cooldowns on **private** parties (voluntary leave only); **host recreate delay** after close (~5 min default, seconds for configured priority roles — role is read **at close time**); audit log channel.
- Optional **gamification** — completions, weekly leaderboard.
- **Web admin** (`/admin`, OAuth) — channels, embed styling (simple + detailed), moderation tiers, **Valorant rank/agent catalog** sync, role mappings, metrics, player-facing site (`/`, `/me`).

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
