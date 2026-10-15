# ADR 002: PostgreSQL como fonte de verdade

## Contexto

Lobbies devem sobreviver a reinícios do bot; o Discord não guarda estado estruturado de vagas/ranks.

## Decisão

Estado em `lobbies` / `lobby_members` / `users`. Embeds e botões são projeções; reconciliação no arranque.

## Alternativas

- Estado só no Discord: perde-se ao apagar mensagens ou reiniciar.
- Event sourcing completo: complexidade desnecessária para o volume atual.

## Consequências

- Sair do lobby nunca expulsa do servidor Discord.
- Migrações Alembic obrigatórias para evolução do modelo.
