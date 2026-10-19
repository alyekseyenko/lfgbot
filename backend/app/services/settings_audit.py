from __future__ import annotations

import json
from typing import Any

from app.db.models import GuildSettings

_MAX_FIELD_LINES = 6

_COLOR_SOURCE_LABELS = {
    "mode": "Modo de jogo",
    "host_rank": "Rank do host",
    "min_rank": "Rank mínimo",
    "max_rank": "Rank máximo",
}

_IMMUNE_KEYS = frozenset(
    {
        "immune_embed_enabled",
        "immune_embed_color",
        "immune_embed_label",
        "immune_embed_tiers",
        "immune_role_ids",
    }
)
_PENALTY_KEYS = frozenset(
    {
        "search_penalty_enabled",
        "search_penalty_early_minutes",
        "search_penalty_early_max_count",
        "search_penalty_mid_minutes",
        "search_penalty_severe_hours",
    }
)
_COOLDOWN_KEYS = frozenset(
    {"host_recreate_cooldown_seconds", "immune_host_recreate_cooldown_seconds"}
)
_EMBED_STYLE_KEYS = frozenset(
    {
        "lfg_embed_color_source",
        "rank_embed_colors",
        "lfg_embed_competitive_color",
        "lfg_embed_unrated_color",
        "lfg_embed_full_color",
        "lfg_embed_inactive_color",
        "lfg_embed_decorative",
        "lfg_embed_footer_brand",
        "lfg_embed_banner_url",
        "lfg_embed_custom_texts",
        "lfg_embed_show_author",
        "lfg_embed_show_timestamp",
        "lfg_embed_show_thumbnail",
        "lfg_embed_banner_on_panel",
        "lfg_embed_banner_on_lobby",
        "lfg_panel_thumbnail_url",
        "lfg_panel_color",
        "lfg_panel_footer_brand",
        "lfg_panel_banner_url",
        "lfg_panel_decorative",
        "lfg_embed_thumbnail_url",
        "lfg_embed_simple",
        "lfg_embed_detailed",
        "lfg_embed_panel",
        "lfg_post_style_simple_enabled",
        "lfg_post_style_detailed_enabled",
    }
)


def _norm_int_list(raw: object) -> list[int]:
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(out)


def _norm_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str)


def _channel_id_as_int(value: object) -> int:
    if value is None or value == "":
        return 0
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return 0
    return 0


def _values_equal(key: str, old: object, new: object) -> bool:
    if key in ("lfg_channel_ids", "immune_role_ids"):
        return _norm_int_list(old) == _norm_int_list(new)
    if key in ("rank_embed_colors", "immune_embed_tiers"):
        return _norm_json(old) == _norm_json(new)
    if key in (
        "stats_channel_id",
        "log_channel_id",
        "announce_channel_id",
        "reputation_channel_id",
        "reputation_negative_role_id",
        "reputation_positive_role_id",
        "guide_channel_id",
    ):
        return _channel_id_as_int(old) == _channel_id_as_int(new)
    return old == new


def filter_changed_settings_patch(row: GuildSettings, patch: dict[str, Any]) -> dict[str, Any]:
    """Ignora campos enviados pelo dashboard mas sem alteração real na BD."""
    changed: dict[str, Any] = {}
    for key, new_val in patch.items():
        old_val = getattr(row, key, None)
        if _values_equal(key, old_val, new_val):
            continue
        changed[key] = new_val
    return changed


def _channel_ref(channel_id: int | None) -> str:
    cid = int(channel_id or 0)
    if cid <= 0:
        return "Desligado"
    return f"<#{cid}>"


def _bool_pt(value: bool) -> str:
    return "Sim" if value else "Não"


def build_dashboard_settings_audit(
    changed: dict[str, Any],
    *,
    username: str,
    user_id: int | None,
) -> tuple[str, str, list[tuple[str, str, bool]]]:
    """Título, descrição e fields do embed Discord (nome, valor, inline)."""
    keys = set(changed.keys())
    if not keys:
        return ("Dashboard", "Sem alterações.", [])

    actor = f"**{username}**"
    if user_id:
        actor = f"<@{user_id}>"

    lines: list[str] = []

    if "lfg_channel_ids" in keys:
        ids = _norm_int_list(changed.get("lfg_channel_ids"))
        if len(ids) == 0:
            lines.append("• Canais LFG: nenhum")
        elif len(ids) <= 3:
            lines.append("• Canais LFG: " + ", ".join(_channel_ref(i) for i in ids))
        else:
            preview = ", ".join(_channel_ref(i) for i in ids[:2])
            lines.append(f"• Canais LFG: {len(ids)} canais ({preview}…)")

    if "log_channel_id" in keys:
        lines.append(f"• Logs de auditoria: {_channel_ref(changed.get('log_channel_id'))}")

    if "stats_channel_id" in keys:
        cid = int(changed.get("stats_channel_id") or 0)
        if cid <= 0:
            lines.append("• Canal de ranking: todos os LFG")
        else:
            lines.append(f"• Canal de ranking: {_channel_ref(cid)}")

    if "announce_channel_id" in keys:
        lines.append(f"• Anúncios: {_channel_ref(changed.get('announce_channel_id'))}")

    if "reputation_channel_id" in keys:
        lines.append(f"• Reputação: {_channel_ref(changed.get('reputation_channel_id'))}")

    if "reputation_delay_minutes" in keys:
        lines.append(
            f"• Atraso reputação: **{int(changed['reputation_delay_minutes'])}** min"
        )

    if "reputation_negative_threshold" in keys:
        lines.append(
            f"• Reputação negativa: ≤ **{int(changed['reputation_negative_threshold'])}** pts"
        )
    if "reputation_negative_role_id" in keys:
        rid = int(changed.get("reputation_negative_role_id") or 0)
        lines.append(
            f"• Role reputação negativa: {'Desligado' if rid <= 0 else f'<@&{rid}>'}"
        )
    if "reputation_positive_threshold" in keys:
        lines.append(
            f"• Reputação positiva: ≥ **{int(changed['reputation_positive_threshold'])}** pts"
        )
    if "reputation_positive_role_id" in keys:
        rid = int(changed.get("reputation_positive_role_id") or 0)
        lines.append(
            f"• Role reputação positiva: {'Desligado' if rid <= 0 else f'<@&{rid}>'}"
        )

    if "weekly_leaderboard_anchor" in keys:
        anchor = changed.get("weekly_leaderboard_anchor")
        if anchor is None:
            lines.append("• Início da semana (criadores): desligado")
        else:
            lines.append(f"• Início da semana (criadores): **{anchor}**")

    if "guide_channel_id" in keys:
        lines.append(f"• Canal do guia: {_channel_ref(changed.get('guide_channel_id'))}")

    if "guide_body" in keys:
        lines.append("• Texto do guia LFG atualizado")

    if "stats_legacy_lobbies_created" in keys:
        lines.append(f"• Histórico (pedidos): **{int(changed['stats_legacy_lobbies_created'])}**")
    if "stats_legacy_joins" in keys:
        lines.append(f"• Histórico (entradas): **{int(changed['stats_legacy_joins'])}**")
    if "stats_legacy_users" in keys:
        lines.append(f"• Histórico (utilizadores): **{int(changed['stats_legacy_users'])}**")

    toggles: list[str] = []
    if "auto_format_messages" in keys:
        toggles.append(f"auto-format {_bool_pt(bool(changed['auto_format_messages']))}")
    if "gamification_enabled" in keys:
        toggles.append(f"gamificação {_bool_pt(bool(changed['gamification_enabled']))}")
    if "panel_sticky_enabled" in keys:
        toggles.append(f"painel sticky {_bool_pt(bool(changed['panel_sticky_enabled']))}")
    if toggles:
        lines.append("• " + " · ".join(toggles))

    if "lobby_ttl_minutes" in keys:
        lines.append(f"• TTL dos pedidos: **{int(changed['lobby_ttl_minutes'])}** min")

    if "party_code_max_length" in keys:
        lines.append(
            f"• Tamanho do código party: **{int(changed['party_code_max_length'])}** caracteres"
        )

    if "default_lfg_mode" in keys:
        lines.append(f"• Modo padrão: **{changed['default_lfg_mode']}**")

    if keys & _EMBED_STYLE_KEYS:
        parts: list[str] = []
        if "lfg_embed_color_source" in keys:
            src = str(changed.get("lfg_embed_color_source", "mode"))
            parts.append(_COLOR_SOURCE_LABELS.get(src, src))
        if "rank_embed_colors" in keys:
            colors = changed.get("rank_embed_colors")
            n = len(colors) if isinstance(colors, dict) else 0
            parts.append(f"{n} cor(es) por rank" if n else "cores por rank")
        lines.append("• Aparência embed: " + " · ".join(parts))

    if keys & _IMMUNE_KEYS:
        tier_count = 0
        tiers = changed.get("immune_embed_tiers")
        if isinstance(tiers, list):
            tier_count = len(tiers)
        enabled = changed.get("immune_embed_enabled")
        if enabled is None and tier_count:
            lines.append(f"• Destaques no embed: **{tier_count}** nível(is)")
        elif enabled is not None:
            state = _bool_pt(bool(enabled))
            tier_suffix = f", {tier_count} níveis" if tier_count else ""
            lines.append(f"• Destaques no embed: {state}{tier_suffix}")
        else:
            lines.append("• Destaques / roles isentas: atualizado")

    if keys & _PENALTY_KEYS:
        if "search_penalty_enabled" in keys:
            lines.append(
                "• Penalizações (party privada): "
                + _bool_pt(bool(changed["search_penalty_enabled"]))
            )
        else:
            lines.append("• Penalizações (party privada): regras ajustadas")

    if keys & _COOLDOWN_KEYS:
        host = changed.get("host_recreate_cooldown_seconds")
        immune = changed.get("immune_host_recreate_cooldown_seconds")
        bits: list[str] = []
        if host is not None:
            bits.append(f"{int(host)} s")
        if immune is not None:
            bits.append(f"{int(immune)} s isentos")
        if bits:
            lines.append("• Cooldown novo pedido: " + " / ".join(bits))

    known = (
        {
            "lfg_channel_ids",
            "log_channel_id",
            "stats_channel_id",
            "announce_channel_id",
            "reputation_channel_id",
            "reputation_delay_minutes",
            "reputation_negative_threshold",
            "reputation_negative_role_id",
            "reputation_positive_threshold",
            "reputation_positive_role_id",
        }
        | _IMMUNE_KEYS
        | _PENALTY_KEYS
        | _COOLDOWN_KEYS
        | _EMBED_STYLE_KEYS
        | {
            "auto_format_messages",
            "gamification_enabled",
            "panel_sticky_enabled",
            "lobby_ttl_minutes",
            "party_code_max_length",
            "default_lfg_mode",
        }
    )
    unknown_keys = keys - known
    if unknown_keys:
        lines.append(f"• Outros: **{len(unknown_keys)}** ajuste(s)")

    if len(lines) > _MAX_FIELD_LINES:
        visible = lines[: _MAX_FIELD_LINES - 1]
        visible.append(f"• … e mais **{len(lines) - _MAX_FIELD_LINES + 1}**")
        lines = visible

    title = "Dashboard · configuração guardada"
    description = f"Alterado por {actor}"
    fields = [("Resumo", "\n".join(lines), False)]
    return title, description, fields
