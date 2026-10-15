# ADR 004: Debounce de edições de embed

## Contexto

Vários jogadores a entrar/sair geram muitos eventos; o Discord limita edições de mensagens.

## Decisão

`EmbedUpdateDebouncer` agrupa `lobby_id` e refresca no intervalo `EMBED_DEBOUNCE_SECONDS`.

## Alternativas

- Editar a cada evento: risco de 429 e custo desnecessário.
- WebSocket próprio para UI: fora de escopo (Discord é a UI).

## Consequências

- Embeds podem atrasar alguns segundos vs BD (aceitável; documentado em SLO).
- Métricas `lfg_embed_events_total` vs `lfg_embed_edits_total` provam poupança.
