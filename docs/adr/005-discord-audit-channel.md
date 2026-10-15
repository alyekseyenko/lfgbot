# ADR 005: Auditoria no canal Discord (não na BD)

## Contexto

Staff quer histórico visível no servidor; RGPD pede minimização de dados.

## Decisão

Guardar só `log_channel_id` em `guild_settings`. Embeds de audit via `send_guild_audit_log`.

## Alternativas

- Tabela `audit_log` na BD: retenção, backups e RGPD mais pesados.
- Serviço externo (SIEM): overkill para comunidade voluntária.

## Consequências

- Histórico desaparece se apagarem mensagens no Discord.
- Custo de BD e queries de leitura nulos para audit.
