# ADR 006: Configuração multi-guild com cache TTL

## Contexto

Vários servidores; dashboard altera `guild_settings` com frequência moderada.

## Decisão

`GuildConfigService` lê da BD e mantém cache em memória com invalidação em PATCH e eventos `guild_join` / `guild_remove`.

## Alternativas

- Só env vars: não escala para SaaS.
- Redis de config: mais um serviço sem necessidade atual.

## Consequências

- Alterações podem levar até um miss de cache se invalidação falhar (paths de escrita invalidam explicitamente).
- Testes unitários mockam ou usam BD de teste.
