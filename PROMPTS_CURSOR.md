# Guia de trabalho com o Cursor: Fase 1 (MVP)

## Preparação (fazes tu, uma vez)

1. Cria a pasta `lfg/` e abre-a no Cursor.
2. Guarda o teu documento de arquitetura como `docs/PROJETO.md`.
3. Copia o ficheiro `projeto.mdc` para `.cursor/rules/projeto.mdc`.
4. `git init`, cria um `.gitignore` (Python, `.env`, `node_modules`) e faz o primeiro commit.
5. No Discord Developer Portal cria a aplicação e o bot de TESTE e guarda o token. Cria também um servidor de teste só teu e convida o bot.
6. Contratar o VPS Hetzner só no passo 8. Até lá tudo corre local com Docker.

## Como usar

- Uma conversa nova do Cursor por passo, em modo **Plan** (revê o plano antes de aprovar).
- Cola o prompt do passo. As regras do projeto já são carregadas automaticamente.
- Depois de gerado: corre os testes, verifica o critério "Feito quando" e só então faz commit.
- Se o Cursor tentar acrescentar coisas fora do passo, responde: "Isso fica para uma fase seguinte. Remove."

---

## Passo 1: Esqueleto do projeto

**Prompt:**
> Lê `docs/PROJETO.md` e as regras do projeto. Implementa apenas o passo 1 da Fase 1: esqueleto do backend. Quero `backend/` com `pyproject.toml` (discord.py, fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, pytest, pytest-asyncio, ruff), estrutura `app/{bot,api,services,db,core}`, configuração via pydantic-settings (DISCORD_TOKEN, DATABASE_URL, LOG_LEVEL), `Dockerfile`, `docker-compose.yml` na raiz com os serviços `app` e `postgres` (com volume e healthcheck), `.env.example` e um `README.md` curto com como arrancar. O `app` deve arrancar, ligar à BD e registar um log "ready". Não implementes bot, modelos nem API. Mostra-me primeiro o plano de ficheiros.

**Feito quando:** `docker compose up` arranca, liga ao Postgres e mostra o log de arranque.

---

## Passo 2: Modelos e migração

**Prompt:**
> Passo 2 da Fase 1. Cria os modelos SQLAlchemy 2.0 (async, tipados) em `app/db/models.py` para `users`, `lobbies` e `lobby_members`, conforme o modelo de dados mínimo das regras. `lobbies.state` é um enum (`open`, `full`, `closed`, `expired`). Restrições: um utilizador só pode ter UMA entrada ativa por lobby (índice único parcial onde `left_at IS NULL`), `slots` entre 1 e 4. Configura o Alembic (async) e gera a primeira migração. Cria `app/db/session.py` com a sessão async. Acrescenta um teste que sobe as tabelas numa BD de teste. Não cries `ratings` nem `moderation_log`.

**Feito quando:** `alembic upgrade head` cria as tabelas e `alembic downgrade base` remove-as sem erros.

---

## Passo 3: Serviço de lobbies (o mais importante)

**Prompt:**
> Passo 3 da Fase 1. Implementa `app/services/lobbies.py` com: `create_lobby(host, mode, slots, party_code, expires_in)`, `join_lobby(lobby_id, user)`, `leave_lobby(lobby_id, user, reason)`, `close_lobby(lobby_id)` e `expire_due_lobbies(now)`. Requisitos: tudo transacional; `join_lobby` é idempotente (entrar 2x não duplica); o host não pode entrar no próprio lobby como membro extra; lobby cheio passa a `full` e devolve erro claro a quem tenta entrar; sair de um `full` volta a `open`; lobbies fechados ou expirados não aceitam entradas; `expire_due_lobbies` devolve a lista de lobbies expirados. Usa locking adequado (`SELECT ... FOR UPDATE`) para evitar condições de corrida. Cada operação emite um evento interno através de um pequeno event bus em `app/core/events.py`. Escreve testes pytest que cubram: entrar 2x, lobby cheio, sair e voltar a entrar, expirar, e duas entradas concorrentes quando resta 1 vaga (só uma pode ter sucesso). Sem nada do Discord neste passo.

**Feito quando:** todos os testes passam, incluindo o de concorrência. **Revê este diff com atenção.**

---

## Passo 4: Bot mínimo com /procurar

**Prompt:**
> Passo 4 da Fase 1. Cria o bot em `app/bot/` e arranca-o no mesmo processo da app. Implementa o slash command `/procurar` com parâmetros `modo` (Competitivo/Unrated), `vagas` (1 a 4) e `codigo` (código da party, opcional se for por convite). O handler só valida, chama `services.lobbies.create_lobby`, e publica uma embed em português com o host, modo, vagas livres, código e a hora de expiração. Guarda `channel_id` e `message_id` no lobby. Garante o registo do utilizador em `users` (upsert) na primeira interação. Sem botões ainda. Restringe o comando aos canais configurados em variável de ambiente (`LFG_CHANNEL_IDS`).

**Feito quando:** `/procurar` no servidor de teste cria o lobby na BD e a embed aparece.

---

## Passo 5: Botões Entrar/Sair e embed sempre atualizada

**Prompt:**
> Passo 5 da Fase 1. Acrescenta à embed os botões Entrar e Sair (discord.ui.View). Os handlers só chamam o serviço e respondem de forma efémera ao utilizador (por exemplo "Já estás neste lobby", "Lobby cheio"). A embed mostra a lista de membros e as vagas livres. A atualização da embed é feita por um listener dos eventos internos do passo 3, com debounce/agrupamento (no máximo uma edição por mensagem a cada ~2 segundos) para respeitar os rate limits. Quando o lobby fica cheio, desativa o botão Entrar. Os `custom_id` dos botões têm de incluir o id do lobby. Testa a lógica de agrupamento de edições com testes unitários.

**Feito quando:** várias pessoas a carregar nos botões deixam a embed coerente com a BD.

---

## Passo 6: Expiração automática

**Prompt:**
> Passo 6 da Fase 1. Cria um job periódico (asyncio task iniciada no arranque, de 30 em 30 segundos) que chama `expire_due_lobbies`, e para cada lobby expirado atualiza a embed (marca como expirado, remove os botões) ou apaga a mensagem, conforme uma variável de configuração `EXPIRED_MODE` (`edit` ou `delete`). O job tem de tolerar erros do Discord (mensagem já apagada, sem permissões) sem parar, e registar o erro em log. Testes para a lógica de seleção de expirados.

**Feito quando:** um lobby com expiração curta desaparece ou fica marcado sozinho.

---

## Passo 7: Botões persistentes após reinício

**Prompt:**
> Passo 7 da Fase 1. Garante que, ao reiniciar o bot, os botões dos lobbies abertos continuam a funcionar: regista as views persistentes no arranque e, para cada lobby `open` ou `full`, volta a associar a view à mensagem e reconcilia a embed com o estado atual da BD. Lobbies que expiraram enquanto o bot estava em baixo são tratados no arranque. Escreve um teste ou, se não for viável, um checklist manual no README.

**Feito quando:** reinicias o container e os botões de um lobby aberto continuam a responder.

---

## Passo 8: Deploy no Hetzner

**Antes:** cria o servidor (por exemplo CX22, Ubuntu LTS), SSH por chave, firewall só com 22/80/443. Confirma o preço atual no site.

**Prompt:**
> Passo 8 da Fase 1. Prepara o deploy: `docker-compose.prod.yml` com `app`, `postgres` e `caddy` (reinício `unless-stopped`, volumes persistentes, Postgres sem porta exposta ao exterior). Um script `scripts/backup.sh` com `pg_dump` comprimido e rotação (manter 14 dias), pensado para correr por cron e enviar o ficheiro para fora da máquina (deixa o destino configurável por variável). Um script `scripts/deploy.sh` que faz pull, build, migrações (`alembic upgrade head`) e reinício. Documenta no README os passos de instalação do servidor. Logs para stdout com nível configurável. Não incluas segredos.

**Feito quando:** o bot fica online 24h no servidor de teste e o backup gera um ficheiro restaurável (testa o restauro uma vez).

---

## Passo 9: Piloto no Unrated

Sem prompt de código. Tarefas tuas:

1. Cria um bot/servidor de produção e restringe `LFG_CHANNEL_IDS` ao canal de Unrated.
2. Anuncia à comunidade que é um teste de uma semana e que escrever no canal continua a ser possível.
3. Regista números reais: pedidos por dia, tempo até o grupo fechar, % de grupos completos.
4. Recolhe feedback e só depois decide a formatação automática da mensagem escrita no canal.

---

## Depois do piloto (cada um com o seu ciclo de passos)

- Formatação automática da mensagem escrita no canal (o hábito atual).
- Fase 2: perfis e histórico de lobbies.
- Fase 3: API + web app (PWA, login Discord OAuth2).
- Fase 4: reputação, avaliações e registo de moderação.

## Se o Cursor se perder

- Reinicia a conversa e cola: "Lê `docs/PROJETO.md` e as regras. Estamos no passo N. Estado atual: [o que já funciona]. Faz só [o que falta]."
- Se o código ficar confuso, volta ao último commit bom (`git restore .` ou `git reset --hard`) em vez de pedir correções em cadeia.
