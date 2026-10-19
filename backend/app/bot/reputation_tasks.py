from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.ranking_embed import build_reputation_leaderboard_embed
from app.core.config import Settings
from app.db.models import LobbyReputationPost, User
from app.services.creator_levels import completed_anchor_week_to_post
from app.services.gamification import (
    PORTUGAL,
    leaderboard_already_posted,
    save_leaderboard_post,
    week_start_for_date,
)
from app.services.guild_config import GuildConfigService
from app.services.reputation import (
    REACTION_THUMBS_DOWN,
    REACTION_THUMBS_UP,
    list_due_lobbies_for_reputation,
    lobby_participant_ids,
    reputation_leaderboard,
    save_reputation_post,
)
from app.services.reputation_embed import build_lobby_reputation_request_embed

logger = logging.getLogger(__name__)


async def _names_for_ids(
    session_factory: async_sessionmaker[AsyncSession], user_ids: list[int]
) -> dict[int, str]:
    if not user_ids:
        return {}
    async with session_factory() as session:
        result = await session.execute(
            select(User.discord_id, User.name).where(User.discord_id.in_(user_ids))
        )
        return {int(row[0]): row[1] for row in result.all()}


async def post_due_reputation_requests(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
) -> None:
    async with session_factory() as session:
        configs = await guild_config.list_guilds_for_reputation(session)

    for config in configs:
        channel_id = int(config.reputation_channel_id or 0)
        if channel_id <= 0 or config.reputation_enabled_at is None:
            continue
        channel = bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("canal de reputação %s inválido", channel_id)
            continue

        async with session_factory() as session:
            due = await list_due_lobbies_for_reputation(
                session,
                discord_guild_id=config.discord_guild_id,
                delay_minutes=config.reputation_delay_minutes,
                enabled_after=config.reputation_enabled_at,
            )

        for lobby in due:
            async with session_factory() as session:
                if await session.get(LobbyReputationPost, lobby.id):
                    continue
                participant_ids = await lobby_participant_ids(session, lobby.id)

            names = await _names_for_ids(session_factory, participant_ids)
            embed = build_lobby_reputation_request_embed(lobby, participant_ids, names)
            try:
                message = await channel.send(embed=embed)
                await message.add_reaction(REACTION_THUMBS_UP)
                await message.add_reaction(REACTION_THUMBS_DOWN)
            except discord.HTTPException:
                logger.exception("falha ao publicar pedido de reputação %s", lobby.id)
                continue

            async with session_factory() as session:
                async with session.begin():
                    await save_reputation_post(
                        session,
                        lobby_id=lobby.id,
                        channel_id=channel.id,
                        message_id=message.id,
                    )
            logger.info("pedido de reputação publicado para lobby %s", lobby.id)


async def reputation_request_loop(
    bot: discord.Client,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
) -> None:
    while True:
        try:
            await post_due_reputation_requests(bot, session_factory, guild_config)
        except Exception:
            logger.exception("reputation request job failed")
        await asyncio.sleep(60)


def _week_start_for_reputation_post(config, now_pt: datetime) -> date | None:
    anchor = config.weekly_leaderboard_anchor
    if anchor is not None:
        week = completed_anchor_week_to_post(now_pt, anchor)
        if week is not None:
            return week
        return None
    if now_pt.weekday() == 6 and now_pt.hour == 21:
        return week_start_for_date(now_pt.date())
    return None


async def maybe_post_weekly_reputation_leaderboard(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
) -> None:
    now_pt = datetime.now(PORTUGAL)
    async with session_factory() as session:
        configs = await guild_config.list_guilds_for_reputation(session)

    for config in configs:
        week_start = _week_start_for_reputation_post(config, now_pt)
        if week_start is None:
            continue
        channel_id = int(config.reputation_channel_id or 0)
        if channel_id <= 0:
            continue

        async with session_factory() as session:
            async with session.begin():
                if await leaderboard_already_posted(session, week_start, channel_id):
                    continue

        channel = bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            continue

        async with session_factory() as session:
            rows = await reputation_leaderboard(
                session, discord_guild_id=config.discord_guild_id, limit=10
            )
        names = await _names_for_ids(session_factory, [r.user_id for r in rows])
        embed = build_reputation_leaderboard_embed(rows, names, week_start=week_start)
        message = await channel.send(embed=embed)

        async with session_factory() as session:
            async with session.begin():
                if await leaderboard_already_posted(session, week_start, channel_id):
                    continue
                await save_leaderboard_post(
                    session,
                    week_start=week_start,
                    channel_id=channel.id,
                    message_id=message.id,
                )


async def reputation_weekly_loop(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
) -> None:
    last_key: str | None = None
    while True:
        try:
            now_pt = datetime.now(PORTUGAL)
            async with session_factory() as session:
                configs = await guild_config.list_guilds_for_reputation(session)
            for config in configs:
                week_start = _week_start_for_reputation_post(config, now_pt)
                if week_start is None:
                    continue
                key = f"rep-{config.discord_guild_id}-{week_start.isoformat()}"
                if key == last_key:
                    continue
                await maybe_post_weekly_reputation_leaderboard(
                    bot, session_factory, guild_config
                )
                last_key = key
        except Exception:
            logger.exception("reputation weekly job failed")
        await asyncio.sleep(60)
