# SLOs operacionais (LFG Valorant)

Objetivos simples, medidos com `/metrics` (Prometheus) e logs. Não são SLAs contratuais — servem para alertas e entrevistas técnicas.

## 1. Ack de interação Discord

**Objetivo:** 99% das interações com botões LFG (`Entrar`, `Sair`, `Fechar`, `Expulsar`) têm primeiro ack em **&lt; 2 s**.

**Medição:** histograma `lfg_interaction_latency_seconds` (observado após `interaction.response` nos handlers de `LobbyView`).

**Alerta sugerido:** `histogram_quantile(0.99, rate(lfg_interaction_latency_seconds_bucket[5m])) > 2` durante 10 min (implementado em `deploy/observability/prometheus/alerts.yml`).

## 2. Consistência após reinício

**Objetivo:** 0 lobbies ativos perdidos após restart do processo (estado na BD reconciliado no `setup_hook`).

**Medição:** log estruturado `reconciled N active lobbies on startup`; testes de integração + verificação manual de que cada lobby ativo tem embed atualizado.

**Critério de falha:** lobby `open`/`full` na BD sem `message_id` ou embed desatualizado &gt; 5 min após restart sem erro nos logs.

## 3. Embeds alinhados com a BD

**Objetivo:** 95% das mudanças de estado refletidas no embed em **≤ 5 s** (debounce + rate limits).

**Medição:** comparar `lfg_embed_events_total` com `lfg_embed_edits_total` (o debounce deve manter `edits << events` em picos); tempo derivado de `EMBED_DEBOUNCE_SECONDS` + latência Discord.

**Nota:** não há timestamp por lobby nas métricas; em produção usar amostragem manual ou trace futuro se necessário.
