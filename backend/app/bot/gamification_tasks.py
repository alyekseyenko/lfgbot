from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.db.models import User
from app.bot.ranking_embed import build_weekly_ranking_embed
from app.services.gamification import (
    PORTUGAL,
    leaderboard_already_posted,
    save_leaderboard_post,
    week_start_for_date,
    weekly_top_hosts,
    weekly_top_players,
)

logger = logging.getLogger(__name__)


async def weekly_leaderboard_embed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    week_start: date | None = None,
) -> discord.Embed:
    now_pt = datetime.now(PORTUGAL)
    week = week_start or week_start_for_date(now_pt.date())

    async with session_factory() as session:
        hosts = await weekly_top_hosts(session, week)
        players = await weekly_top_players(session, week)

    user_ids = {e.user_id for e in hosts} | {e.user_id for e in players}
    name_for_id: dict[int, str] = {}
    if user_ids:
        async with session_factory() as session:
            result = await session.execute(
                select(User.discord_id, User.name).where(User.discord_id.in_(user_ids))
            )
            name_for_id = {int(row[0]): row[1] for row in result.all()}

    return build_weekly_ranking_embed(week, hosts, players, name_for_id)


async def maybe_post_weekly_leaderboard(
    bot: discord.Client,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    channel_ids = settings.stats_post_channel_ids()
    if not settings.gamification_enabled or not channel_ids:
        return

    now_pt = datetime.now(PORTUGAL)
    week_start = week_start_for_date(now_pt.date())
    embed = await weekly_leaderboard_embed(session_factory, week_start=week_start)

    for channel_id in channel_ids:
        async with session_factory() as session:
            async with session.begin():
                if await leaderboard_already_posted(session, week_start, channel_id):
                    continue

        channel = bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning("canal de ranking %s inválido ou inacessível", channel_id)
            continue

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

        logger.info(
            "leaderboard semanal publicado para semana %s no canal %s",
            week_start,
            channel_id,
        )


async def leaderboard_loop(
    bot: discord.Client,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    last_post_key: str | None = None
    while True:
        try:
            if settings.gamification_enabled and settings.stats_post_channel_ids():
                now_pt = datetime.now(PORTUGAL)
                key = f"{now_pt.date().isoformat()}-21"
                if now_pt.weekday() == 6 and now_pt.hour == 21 and key != last_post_key:
                    await maybe_post_weekly_leaderboard(bot, settings, session_factory)
                    last_post_key = key
        except Exception:
            logger.exception("leaderboard job failed")
        await asyncio.sleep(60)
