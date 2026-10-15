from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import discord

from app.services.gamification import WeeklyEntry

_RANK_COLOUR = discord.Colour.from_rgb(255, 90, 95)
_MEDALS = ("🥇", "🥈", "🥉")


def _week_range_label(week_start: date) -> str:
    week_end = week_start + timedelta(days=6)
    return f"{week_start.day:02d}/{week_start.month:02d} – {week_end.day:02d}/{week_end.month:02d}"


def _format_top_list(
    entries: list[WeeklyEntry],
    name_for_id: dict[int, str],
    *,
    unit: str,
) -> str:
    if not entries:
        return "_Sem dados esta semana._"
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        prefix = _MEDALS[index - 1] if index <= len(_MEDALS) else f"**{index}.**"
        name = name_for_id.get(entry.user_id, str(entry.user_id))
        lines.append(f"{prefix} **{name}** · `{entry.count}` {unit}")
    return "\n".join(lines)


def build_weekly_ranking_embed(
    week_start: date,
    hosts: list[WeeklyEntry],
    players: list[WeeklyEntry],
    name_for_id: dict[int, str],
) -> discord.Embed:
    range_label = _week_range_label(week_start)
    embed = discord.Embed(
        title="Ranking LFG",
        description=(
            f"Semana **{range_label}** (hora de Lisboa)\n"
            "Conta apenas **grupos completos** registados pelo bot."
        ),
        colour=_RANK_COLOUR,
        timestamp=datetime.now(UTC),
    )

    embed.add_field(
        name="Top hosts",
        value=_format_top_list(hosts, name_for_id, unit="como host"),
        inline=True,
    )
    embed.add_field(
        name="Top jogadores",
        value=_format_top_list(players, name_for_id, unit="como jogador"),
        inline=True,
    )

    total_host = sum(e.count for e in hosts)
    total_player = sum(e.count for e in players)
    embed.add_field(
        name="Resumo",
        value=(
            f"Entradas no top: **{len(hosts)}** hosts · **{len(players)}** jogadores\n"
            f"Soma no top: **{total_host}** · **{total_player}** grupos"
        ),
        inline=False,
    )

    embed.set_footer(text="Novo ranking à segunda-feira · usa /ranking para atualizar")
    return embed
