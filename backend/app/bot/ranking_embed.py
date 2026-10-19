from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import discord

from app.services.gamification import WeeklyEntry
from app.services.reputation import ReputationLeaderboardEntry

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
    empty: str = "_Sem dados esta semana._",
) -> str:
    if not entries:
        return empty
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


def _format_top_list_from_rank(
    entries: list[WeeklyEntry],
    name_for_id: dict[int, str],
    *,
    start_rank: int,
    unit: str,
    empty: str,
) -> str:
    if not entries:
        return empty
    lines: list[str] = []
    for index, entry in enumerate(entries):
        rank = start_rank + index
        prefix = _MEDALS[rank - 1] if 1 <= rank <= len(_MEDALS) else f"**{rank}.**"
        name = name_for_id.get(entry.user_id, str(entry.user_id))
        lines.append(f"{prefix} **{name}** · `{entry.count}` {unit}")
    return "\n".join(lines)


def build_all_time_creators_embed(
    entries: list[WeeklyEntry],
    name_for_id: dict[int, str],
    *,
    page: int = 1,
    page_size: int = 10,
) -> discord.Embed:
    start_rank = (page - 1) * page_size + 1
    embed = discord.Embed(
        title="Ranking LFG · Grupos criados",
        description=(
            "Histórico **completo** (sem limite de tempo).\n"
            "Conta **pedidos LFG criados** neste servidor."
        ),
        colour=_RANK_COLOUR,
        timestamp=datetime.now(UTC),
    )
    embed.add_field(
        name=f"Página {page}",
        value=_format_top_list_from_rank(
            entries,
            name_for_id,
            start_rank=start_rank,
            unit="grupos",
            empty="_Ninguém nesta página (ou ainda sem dados)._",
        ),
        inline=False,
    )
    total = sum(e.count for e in entries)
    embed.set_footer(text=f"Página {page} · /ranking pagina:{page + 1} · 10 por página")
    if entries:
        embed.add_field(
            name="Resumo (esta página)",
            value=f"**{len(entries)}** pessoas · **{total}** grupos listados",
            inline=False,
        )
    return embed


def build_creator_level_up_embed(
    *,
    level_name: str,
    level_number: int,
    rooms_created: int,
) -> discord.Embed:
    embed = discord.Embed(
        title="Nível de criador",
        description=(
            f"Chegaste a **{level_name}** (nível **{level_number}**) — "
            f"**{rooms_created}** grupo{'s' if rooms_created != 1 else ''} criado"
            f"{'s' if rooms_created != 1 else ''}."
        ),
        colour=discord.Colour.from_rgb(88, 180, 255),
        timestamp=datetime.now(UTC),
    )
    embed.set_footer(text="Níveis de criador · grupos criados neste servidor")
    return embed


def build_weekly_creators_embed(
    week_start: date,
    entries: list[WeeklyEntry],
    name_for_id: dict[int, str],
) -> discord.Embed:
    range_label = _week_range_label(week_start)
    embed = discord.Embed(
        title="Top criadores da semana",
        description=(
            f"Semana **{range_label}** (hora de Lisboa)\n"
            "Conta **grupos criados** neste período."
        ),
        colour=_RANK_COLOUR,
        timestamp=datetime.now(UTC),
    )
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        prefix = _MEDALS[index - 1] if index <= len(_MEDALS) else f"**{index}.**"
        name = name_for_id.get(entry.user_id, str(entry.user_id))
        lines.append(f"{prefix} <@{entry.user_id}> · **{name}** · `{entry.count}` grupos")
    embed.add_field(
        name="Top 10",
        value="\n".join(lines) if lines else "_Sem grupos criados nesta semana._",
        inline=False,
    )
    embed.set_footer(text="Ranking semanal de criadores")
    return embed


def build_reputation_leaderboard_embed(
    entries: list[ReputationLeaderboardEntry],
    name_for_id: dict[int, str],
    *,
    week_start: date | None = None,
    page: int = 1,
    page_size: int = 10,
) -> discord.Embed:
    title = "Ranking de reputação LFG"
    if week_start is not None:
        range_label = _week_range_label(week_start)
        description = (
            f"Semana **{range_label}** (hora de Lisboa)\n"
            "Pontuação **acumulada** (👍/👎 nos pedidos de reputação)."
        )
    else:
        description = (
            "Pontuação **acumulada** com votos 👍/👎 nos pedidos de reputação.\n"
            "Não mede desempenho in-game — só o grupo Discord."
        )
    embed = discord.Embed(
        title=title,
        description=description,
        colour=_RANK_COLOUR,
        timestamp=datetime.now(UTC),
    )
    start_rank = (page - 1) * page_size + 1
    if not entries:
        embed.add_field(name=f"Página {page}", value="_Ainda sem votos ou página vazia._", inline=False)
    else:
        lines: list[str] = []
        for index, entry in enumerate(entries):
            rank = start_rank + index
            prefix = _MEDALS[rank - 1] if 1 <= rank <= len(_MEDALS) else f"**{rank}.**"
            name = name_for_id.get(entry.user_id, str(entry.user_id))
            sign = "+" if entry.score >= 0 else ""
            lines.append(f"{prefix} **{name}** · `{sign}{entry.score}`")
        embed.add_field(name=f"Página {page}", value="\n".join(lines), inline=False)
    embed.set_footer(text=f"Página {page} · /reputacao pagina:{page + 1} · 10 por página")
    return embed


RANKING_PAGE_SIZE = 10


async def reputation_leaderboard_embed(
    session_factory,
    *,
    discord_guild_id: int,
    page: int = 1,
    page_size: int = RANKING_PAGE_SIZE,
) -> discord.Embed:
    from sqlalchemy import select

    from app.db.models import User
    from app.services.reputation import reputation_leaderboard

    page = max(1, page)
    offset = (page - 1) * page_size
    async with session_factory() as session:
        rows = await reputation_leaderboard(
            session,
            discord_guild_id=discord_guild_id,
            limit=page_size,
            offset=offset,
        )
    user_ids = [r.user_id for r in rows]
    name_for_id: dict[int, str] = {}
    if user_ids:
        async with session_factory() as session:
            result = await session.execute(
                select(User.discord_id, User.name).where(User.discord_id.in_(user_ids))
            )
            name_for_id = {int(row[0]): row[1] for row in result.all()}
    return build_reputation_leaderboard_embed(
        rows, name_for_id, page=page, page_size=page_size
    )


async def all_time_creators_embed_paged(
    session_factory,
    *,
    discord_guild_id: int,
    page: int = 1,
    page_size: int = RANKING_PAGE_SIZE,
) -> discord.Embed:
    from sqlalchemy import select

    from app.db.models import User
    from app.services.creator_levels import all_time_top_creators

    page = max(1, page)
    offset = (page - 1) * page_size
    async with session_factory() as session:
        rows = await all_time_top_creators(
            session,
            discord_guild_id=discord_guild_id,
            limit=page_size,
            offset=offset,
        )
    entries = [WeeklyEntry(user_id=row.user_id, count=row.count) for row in rows]
    user_ids = {e.user_id for e in entries}
    name_for_id: dict[int, str] = {}
    if user_ids:
        async with session_factory() as session:
            result = await session.execute(
                select(User.discord_id, User.name).where(User.discord_id.in_(user_ids))
            )
            name_for_id = {int(row[0]): row[1] for row in result.all()}
    return build_all_time_creators_embed(
        entries, name_for_id, page=page, page_size=page_size
    )


def weekly_creators_mention_content(entries: list[WeeklyEntry]) -> str:
    if not entries:
        return ""
    mentions = " ".join(f"<@{entry.user_id}>" for entry in entries)
    return f"Parabéns aos criadores da semana! {mentions}"
