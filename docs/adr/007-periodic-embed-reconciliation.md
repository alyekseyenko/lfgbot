# ADR 007: Reconciliação periódica de embeds

## Contexto

O event bus publica após commit em memória (ADR 003). Se o processo morrer entre o commit e o listener, a BD está correcta mas o embed no Discord pode ficar desatualizado até ao próximo evento.

No arranque já reconciliamos lobbies activos (`_reconcile_on_startup` em `app/bot/client.py`).

## Decisão

Job periódico (`embed_reconciliation_loop`) que lista lobbies `open`/`full` na BD e chama `EmbedUpdater.refresh_now` para cada um, no intervalo `RECONCILE_POLL_SECONDS` (default 300).

Não comparamos campo-a-campo com a mensagem Discord: a projeção correcta é sempre derivada da BD; refrescar periodicamente é barato com poucos lobbies activos e fecha o buraco at-most-once sem nova infra.

## Alternativas

- **Outbox table:** entrega durável entre processos; adoptar quando existir mais de uma instância ou requisito de entrega garantida entre serviços.
- **Redis pub/sub:** mesma história de escala.
- **Só reconciliar no boot:** insuficiente para crash sem restart imediato.

## Consequências

- Edições extra no Discord (limitadas pelo número de lobbies activos e debounce interno do updater); monitorizar `lfg_embed_edits_total` e alertas.
- Com muitos lobbies activos sustentados, rever intervalo ou passar a outbox + fila de edições (ver ARCHITECTURE.md).
