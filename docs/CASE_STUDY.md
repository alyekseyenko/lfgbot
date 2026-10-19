# Case study — Plataforma LFG Valorant (PT)

## Problema

Comunidade Discord de Valorant (~13 mil membros) com canais de procura (competitivo, unrated, scrims, etc.) **desorganizados em chat**: moderadores sempre de olho, códigos repetidos ou desatualizados, sem controlo de entradas/saídas, queixas de toxicidade e ~**450** procuras/dia em média. Após a plataforma LFG, o último cálculo interno apontou ~**1,250** procuras/dia **estruturadas**, com menos carga reactiva na moderação.

## Restrições

- **Discord** é a única UI dos jogadores; rate limits e menções impõem como mostrar host e código.
- **RGPD**: guardar o mínimo (IDs Discord, ranks, histórico de lobbies); sair de um lobby não pode expulsar do servidor.
- **Operação**: um VPS, equipa pequena; um token de bot = uma instância.

## Decisões de arquitectura

| Decisão | Motivo |
|---------|--------|
| Monólito bot + API | Mesmo domínio de dados, deploy simples, eventos após commit no mesmo processo ([ADR 001](adr/001-monolith-bot-and-api.md)) |
| PostgreSQL fonte de verdade | Lobbies sobrevivem a reinícios; embeds são projeção ([ADR 002](adr/002-postgres-source-of-truth.md)) |
| Tenant = `discord_guild_id` | Multi-servidor com config via dashboard sem redeploy ([ADR 006](adr/006-multi-guild-config-cache.md)) |
| Debounce de embeds | Picos de Entrar/Sair sem 429 ([ADR 004](adr/004-embed-debounce.md)) |
| Reputação com `reputation_enabled_at` | Sem backlog histórico ao activar canal; só pedidos novos |

## Resultados

### Impacto na comunidade (totais lifetime)

| Métrica | Valor | Fonte |
|---------|-------|--------|
| Pedidos de grupo (lifetime) | **384,931+** | Baseline legado em `guild_settings` + `lobbies` desde deploy |
| Entradas / joins (lifetime) | **1,154,793+** | Baseline legado + `lobby_members` / métricas bot |
| Jogadores LFG distintos | **8,200+** | Estimativa legado + `users` |
| Membros no Discord | **~13,000** | Comunidade alvo |

### Sinais de engenharia (instrumentados)

| Métrica | Objectivo / estado | Onde medir |
|---------|-------------------|------------|
| Ack de botões (p99) | **&lt; 2 s** (SLO) | `lfg_interaction_latency_seconds` em `/metrics` |
| Consistência após restart | 0 lobbies activos “perdidos” | Log `reconciled N active lobbies`; job periódico [ADR 007](adr/007-periodic-embed-reconciliation.md) |
| Embeds vs BD | **95%** em ≤ 5 s (debounce + Discord) | `lfg_embed_events_total` vs `lfg_embed_edits_total` |
| Qualidade | **170+** testes pytest | CI `backend/tests/` |
| Pedidos / dia (bot era) | _Atualizar em produção_ | `/lfg-stats` ou `lfg_lobbies_created_total` |
| % grupos cheios | _Atualizar em produção_ | `filled_at` / lobbies criados |

Substitui as duas últimas linhas com valores reais do teu ambiente quando fizeres refresh trimestral do case study.

## Frases para CV

- **Transformation / produto:** Estruturei o LFG de uma comunidade ~13k (384k+ pedidos lifetime) com bot Discord, admin OAuth e Postgres como fonte de verdade, substituindo anos de chat manual por fluxo medido.
- **Arquitectura:** Monólito bot+API multi-guild, eventos de domínio, debounce de embeds, reconciliação periódica, SLOs Prometheus e 7 ADRs documentados.
- **Entrega:** Docker em VPS, runbook, RGPD (`/lfg-apagar-dados`), reputação LFG com governação (staff, roles por score, ajustes auditados).

## Trade-offs para entrevista

1. **Monólito vs microserviços** — O limite é o gateway Discord (1 token), não o acoplamento Python.
2. **Event bus em memória vs outbox** — At-most-once entre commit e embed é aceitável com reconciliação; outbox quando houver mais de um processo.
3. **Embed atrasado (debounce) vs editar a cada evento** — Segundos de atraso vs risco de 429; SLO de 95% em ≤ 5 s ([SLO.md](SLO.md)).
