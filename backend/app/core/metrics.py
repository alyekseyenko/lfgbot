"""Métricas Prometheus (endpoint /metrics na API)."""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

lobbies_created_total = Counter(
    "lfg_lobbies_created_total",
    "Lobbies criados",
    ["source"],
)
joins_total = Counter("lfg_joins_total", "Entradas em lobbies bem-sucedidas")
lobby_time_to_fill_seconds = Histogram(
    "lfg_lobby_time_to_fill_seconds",
    "Segundos entre criação e lobby cheio",
    buckets=(30, 60, 120, 300, 600, 1800, 3600),
)
interaction_latency_seconds = Histogram(
    "lfg_interaction_latency_seconds",
    "Tempo até primeiro ack da interação Discord",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0),
)
embed_events_total = Counter("lfg_embed_events_total", "Eventos que pedem atualização de embed")
embed_edits_total = Counter("lfg_embed_edits_total", "Edições de embed efectuadas (após debounce)")
embed_reconcile_runs_total = Counter(
    "lfg_embed_reconcile_runs_total",
    "Execuções do job de reconciliação periódica de embeds",
)
embed_reconcile_lobbies_total = Counter(
    "lfg_embed_reconcile_lobbies_total",
    "Lobbies com refresh_now durante reconciliação periódica",
)
discord_http_errors_total = Counter(
    "lfg_discord_http_errors_total",
    "Erros HTTP do Discord ao editar/apagar mensagens",
    ["status"],
)


def observe_lobby_filled(created_at_ts: float, filled_at_ts: float) -> None:
    delta = max(0.0, filled_at_ts - created_at_ts)
    lobby_time_to_fill_seconds.observe(delta)


def metrics_payload() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
