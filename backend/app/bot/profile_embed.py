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
    role_name_for_level,
)


@dataclass(frozen=True, slots=True)
class ProfileEmbedBuild:
    embed: discord.Embed
    mention_role_ids: list[int]


def _level_color(level: str) -> discord.Colour:
    if level == LEVEL_RADIANTE:
        return discord.Colour.from_rgb(255, 200, 60)
    if level == LEVEL_AGENTE:
        return discord.Colour.from_rgb(90, 160, 255)
    if level == LEVEL_RECRUTA:
        return discord.Colour.from_rgb(80, 200, 120)
    return discord.Colour.from_rgb(120, 120, 128)


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


def _lfg_role_line(guild: discord.Guild | None, level: str, mention_ids: list[int]) -> str:
    role_name = role_name_for_level(level)
    if role_name is None:
        return "Completa **1 grupo** (cheio, ≥3 min) para desbloqueares **LFG Recruta**."
    if guild is None:
        return f"Cargo LFG: **{role_name}**"
    role = discord.utils.get(guild.roles, name=role_name)
    if role is None:
        return f"Cargo LFG: **{role_name}** _(cria a role no servidor)_"
    mention_ids.append(role.id)
    return f"Cargo LFG: {role.mention}"


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
) -> ProfileEmbedBuild:
    mention_ids: list[int] = []
    level_label = stats.level if stats.level != LEVEL_NONE else "Sem nível"

    description_lines = [
        f"## {level_label}",
        _lfg_role_line(guild, stats.level, mention_ids),
        _valorant_rank_line(guild, valorant_rank, mention_ids),
    ]

    embed = discord.Embed(
        colour=_level_color(stats.level),
        description="\n".join(description_lines),
        timestamp=datetime.now(UTC),
    )
    embed.set_author(name=display_name, icon_url=avatar_url)
    embed.title = "Perfil LFG"

    embed.add_field(name="Host", value=f"**{stats.host_completions}**", inline=True)
    embed.add_field(name="Jogador", value=f"**{stats.player_completions}**", inline=True)
    embed.add_field(name="Total", value=f"**{stats.total_completions}**", inline=True)

    if stats.kicks_received > 0:
        embed.add_field(
            name="Expulsões (bot)",
            value=f"**{stats.kicks_received}**",
            inline=True,
        )

    embed.add_field(
        name="Próximo nível",
        value=format_progress_block(stats.host_completions, stats.total_completions),
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
