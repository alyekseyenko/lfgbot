# ADR 001: Monólito bot + API

## Contexto

Comunidade ~13k; um VPS; equipa pequena. Precisamos de bot Discord e dashboard OAuth no mesmo domínio de dados.

## Decisão

Um processo Python: discord.py + FastAPI/uvicorn, partilhando `session_factory` e `EventBus`.

## Alternativas

- Microserviços (bot vs API): mais deploy e latência entre serviços, sem ganho nesta fase.
- Bot sem API: obriga config só por env, inaceitável para multi-guild SaaS.

## Consequências

- Deploy simples (Docker Compose).
- Escala horizontal limitada ao modelo Discord (um gateway por token).
- Testes de integração cobrem bot e API juntos.
