from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import discord

from app.bot.discord_roles import rank_label_for_guild
from app.services.gamification import (
    LEVEL_AGENTE,
    LEVEL_NONE,
    LEVEL_RADIANTE,
    LEVEL_RECRUTA,
    ProfileStats,
    RecentCompletion,
    level_from_counts,
    progress_bar,
)


@dataclass(frozen=True, slots=True)
class ProfileEmbedBuild:
    embed: discord.Embed
    mention_role_ids: list[int]


def _level_color(level_number: int) -> discord.Colour:
    palette = (
        (120, 120, 128),
        (80, 200, 120),
        (90, 160, 255),
        (180, 110, 255),
        (255, 160, 60),
        (255, 200, 60),
    )
    if level_number <= 0:
        return discord.Colour.from_rgb(*palette[0])
    rgb = palette[min(level_number, len(palette) - 1)]
    return discord.Colour.from_rgb(*rgb)


def _relative_pt(when: datetime, now: datetime) -> str:
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    delta = now - when.astimezone(UTC)
    days = delta.days
    if days > 0:
        return f"há {days} dia{'s' if days != 1 else ''}"
    hours = delta.seconds // 3600
    if hours > 0:
        return f"há {hours} h"
    minutes = max(1, delta.seconds // 60)
    return f"há {minutes} min"


def _kind_label_pt(kind: str) -> str:
    return "Host" if kind == "host" else "Jogador"


def format_creator_progress(stats: ProfileStats) -> str:
    rooms = stats.rooms_created
    if stats.next_min_rooms is None:
        bar = progress_bar(10, 10, width=12)
        return f"```\n{stats.level} · nível máximo\n{rooms} grupos criados\n{bar}\n```"
    goal = stats.next_min_rooms
    bar = progress_bar(rooms, goal, width=12)
    return f"```\n{stats.level} · {rooms}/{goal} grupos\n{bar}\n```"


def _valorant_rank_line(
    guild: discord.Guild | None,
    rank: str | None,
    mention_ids: list[int],
) -> str:
    if not rank:
        return "Rank Valorant: _não definido no bot_"
    label = rank_label_for_guild(guild, rank, mention_ids, with_role_emoji=True)
    if label:
        return f"Rank Valorant: {label}"
    return f"Rank Valorant: **{rank}**"


def format_progress_block(host_count: int, total: int) -> str:
    level = level_from_counts(host_count, total)
    if level == LEVEL_RADIANTE:
        return "```\nRadiante · nível máximo\n▰▰▰▰▰▰▰▰▰▰\n```"
    if level == LEVEL_NONE:
        bar = progress_bar(total, 1, width=12)
        return f"```\nRecruta · {total}/1 grupo\n{bar}\n```"
    if level == LEVEL_RECRUTA:
        host_bar = progress_bar(host_count, 3, width=12)
        total_bar = progress_bar(total, 5, width=12)
        return (
            "```\nAgente · 3 host OU 5 total\n"
            f"Host  {host_count:>2}/3  {host_bar}\n"
            f"Total {total:>2}/5  {total_bar}\n```"
        )
    bar = progress_bar(total, 20, width=12)
    return f"```\nRadiante · {total}/20\n{bar}\n```"


def format_recent_completions(recent: list[RecentCompletion]) -> str:
    if not recent:
        return "_Ainda sem grupos completos._"
    now = datetime.now(UTC)
    lines: list[str] = []
    for index, entry in enumerate(recent, start=1):
        when = _relative_pt(entry.awarded_at, now)
        mode = entry.mode
        lines.append(f"`{index}.` **{mode}** · {_kind_label_pt(entry.kind)} · {when}")
    return "\n".join(lines)


def build_profile_embed(
    stats: ProfileStats,
    *,
    display_name: str,
    guild: discord.Guild | None = None,
    valorant_rank: str | None = None,
    last_completed_at: datetime | None = None,
    recent: list[RecentCompletion] | None = None,
    avatar_url: str | None = None,
    reputation_score: int | None = None,
) -> ProfileEmbedBuild:
    mention_ids: list[int] = []
    level_label = stats.level if stats.level not in (LEVEL_NONE, "—") else "Sem nível"

    description_lines = [
        f"## Criador · {level_label}",
        f"Salas criadas: **{stats.rooms_created}** (histórico completo)",
        _valorant_rank_line(guild, valorant_rank, mention_ids),
    ]

    embed = discord.Embed(
        colour=_level_color(stats.creator_level_number),
        description="\n".join(description_lines),
        timestamp=datetime.now(UTC),
    )
    embed.set_author(name=display_name, icon_url=avatar_url)
    embed.title = "Perfil LFG"

    embed.add_field(name="Grupos criados", value=f"**{stats.rooms_created}**", inline=True)
    embed.add_field(name="Completos (host)", value=f"**{stats.host_completions}**", inline=True)
    embed.add_field(name="Completos (jogador)", value=f"**{stats.player_completions}**", inline=True)

    if reputation_score is not None:
        sign = "+" if reputation_score > 0 else ""
        embed.add_field(
            name="Reputação LFG",
            value=f"**{sign}{reputation_score}**",
            inline=True,
        )

    if stats.kicks_received > 0:
        embed.add_field(
            name="Expulsões (bot)",
            value=f"**{stats.kicks_received}**",
            inline=True,
        )

    embed.add_field(
        name="Próximo nível de criador",
        value=format_creator_progress(stats),
        inline=False,
    )

    if recent is not None:
        embed.add_field(
            name="Histórico recente",
            value=format_recent_completions(recent),
            inline=False,
        )
    elif last_completed_at is not None:
        embed.add_field(
            name="Histórico recente",
            value=f"Último grupo: {_relative_pt(last_completed_at, datetime.now(UTC))}",
            inline=False,
        )

    embed.set_footer(text=stats.next_level_hint)
    return ProfileEmbedBuild(embed=embed, mention_role_ids=mention_ids)
