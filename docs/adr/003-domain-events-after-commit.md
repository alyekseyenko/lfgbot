# ADR 003: Event bus em memória com publicação após commit

## Contexto

Listeners (embeds, audit, gamificação) leem a BD. Publicar eventos dentro da transação causava `LobbyNotFound` e retries frágeis.

## Decisão

`queue_domain_event(session, …)` acumula na `session.info`; hooks SQLAlchemy `after_commit` / `after_rollback` publicam ou descartam.

## Alternativas

- **Outbox table:** entrega durável; útil com múltiplas instâncias — não necessário com um processo.
- **Redis pub/sub:** mesma história de escala.

## Consequências

- Entrega at-most-once em memória; se o processo morrer entre commit e `publish`, a BD continua correta e o arranque reconcilia embeds.
- Sem tabela extra nem infraestrutura de fila.
