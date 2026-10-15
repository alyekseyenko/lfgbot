# Sistema LFG Valorant — Descrição e arquitetura

## 1. Contexto

Comunidade portuguesa de Valorant no Discord com cerca de 13 mil membros, muito ativa. Todos os dias as pessoas procuram colegas de jogo nos canais de Competitivo e Unrated, escrevendo mensagens do tipo «procuro 2» com o código da party. O hábito está enraizado há 3 a 4 anos; a solução deve melhorar o processo sem o substituir de forma brusca.

## 2. Problema

- Mensagens com formatos diferentes, difíceis de ler e de filtrar.
- Pedidos antigos ficam no canal depois de a party estar cheia.
- Sem reputação nem histórico: expulsões de lobbies sem motivo e sem consequências.
- Sem perfis nem estatísticas internas da comunidade.

## 3. Objetivos

- Formatar pedidos de forma uniforme, mantendo o hábito de escrever no canal.
- Entrar e sair do lobby por botões, com estado sempre atualizado.
- Perfis, reputação e histórico de expulsões com motivo (fases posteriores).
- Mais tarde: web app (PWA) sincronizada com o Discord, login via Discord OAuth2.
- Medir impacto: pedidos por dia, tempo até o grupo fechar, taxa de grupos completos.

## 4. Arquitetura

```
Discord -> Bot (discord.py)
              |
              v
     Núcleo (lobbies, matching, reputação)
              |
      +-------+--------+
      v                v
 PostgreSQL        API REST + WebSocket -> Web app (PWA, React/TS)
```

- Monólito: um processo com bot + API + lógica.
- Base de dados como fonte de verdade; Discord é apresentação.
- Eventos internos para bot e (fase 3) WebSocket.

## 5. Stack

| Camada | Tecnologia |
|--------|------------|
| Backend | Python 3.12, discord.py, FastAPI, SQLAlchemy 2 async, Alembic |
| Base de dados | PostgreSQL |
| Front-end (fase 3) | React, Vite, TypeScript, PWA |
| Deploy | Docker Compose → VPS (Hetzner) |

## 6. Modelo de dados mínimo (fase 1)

- **users** — discord_id, name, rank, created_at
- **lobbies** — id, host_id, mode, slots, party_code, state, expires_at, channel_id, message_id
- **lobby_members** — lobby_id, user_id, joined_at, left_at, leave_reason

`ratings` e `moderation_log` na fase 4.

## 7. Fases

1. **MVP (~1 semana):** `/procurar` ou formatação automática, embed com botões, expiração, PostgreSQL. Piloto no Unrated.
2. Perfis e histórico de lobbies.
3. API + PWA com OAuth2 Discord.
4. Reputação, avaliações e moderação.

## 8. RGPD

Guardar o mínimo necessário; informar a comunidade; permitir remoção de dados a pedido.

## 9. Métricas de sucesso

Pedidos por dia, tempo médio até fechar grupo, % grupos completos, utilizadores ativos, redução de expulsões sem motivo.
