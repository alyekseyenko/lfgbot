from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User, ValorantPlayerCard, ValorantRank
from app.services.gamification import ProfileStats, profile_stats, recent_completions
from app.services.ranks import normalize_rank_name
from app.services.riot_id import format_riot_id


@dataclass(frozen=True, slots=True)
class AgentSummary:
    uuid: str
    display_name: str
    role_name: str
    display_icon_url: str | None
    full_portrait_url: str | None
    abilities: list[dict[str, str | None]]


@dataclass(frozen=True, slots=True)
class PlayerProfileView:
    discord_id: int
    name: str
    rank_label: str | None
    rank_icon_url: str | None
    riot_id: str | None
    stats: ProfileStats
    recent: list[tuple[str, str, datetime]]
    agents: list[AgentSummary]
    player_card_uuid: str | None
    player_card_wide_url: str | None
    is_self: bool


async def _rank_summary(session: AsyncSession, rank: str | None) -> tuple[str | None, str | None]:
    if not rank:
        return None, None
    normalized = normalize_rank_name(rank)
    result = await session.execute(select(ValorantRank))
    ranks = list(result.scalars())
    for row in ranks:
        if normalize_rank_name(row.display_name) == normalized:
            return row.display_name, row.small_icon_url
    return rank, None


async def _default_player_card(session: AsyncSession) -> ValorantPlayerCard | None:
    result = await session.execute(select(ValorantPlayerCard).limit(1))
    return result.scalar_one_or_none()


async def _resolve_player_card(
    session: AsyncSession,
    user: User,
) -> tuple[str | None, str | None]:
    if user.player_card_uuid:
        card = await session.get(ValorantPlayerCard, user.player_card_uuid)
        if card is not None:
            return card.uuid, card.wide_art_url
    fallback = await _default_player_card(session)
    if fallback is None:
        return None, None
    return None, fallback.wide_art_url


async def build_player_profile(
    session: AsyncSession,
    _bot: discord.Client | None,
    *,
    target_id: int,
    viewer_id: int | None,
    guild_ids: list[int],
    include_riot_id: bool,
) -> PlayerProfileView | None:
    user = await session.get(User, target_id)
    if user is None:
        return None

    guild_id = guild_ids[0] if guild_ids else None
    stats = await profile_stats(session, target_id, discord_guild_id=guild_id)
    recent_rows = await recent_completions(session, target_id, limit=5)
    recent = [(r.mode, r.kind, r.awarded_at) for r in recent_rows]
    rank_label, rank_icon = await _rank_summary(session, user.rank)

    riot_id = None
    if include_riot_id:
        riot_id = format_riot_id(user.riot_game_name, user.riot_tag)

    card_uuid, wide = await _resolve_player_card(session, user)

    return PlayerProfileView(
        discord_id=target_id,
        name=user.name,
        rank_label=rank_label or user.rank,
        rank_icon_url=rank_icon,
        riot_id=riot_id,
        stats=stats,
        recent=recent,
        agents=[],
        player_card_uuid=card_uuid,
        player_card_wide_url=wide,
        is_self=viewer_id == target_id,
    )
