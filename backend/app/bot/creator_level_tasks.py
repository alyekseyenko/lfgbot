from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.ranking_embed import (
    build_weekly_creators_embed,
    weekly_creators_mention_content,
)
from app.core.config import Settings
from app.db.models import User
from app.services.creator_levels import (
    completed_anchor_week_to_post,
    weekly_top_creators_in_anchor_week,
)
from app.services.gamification import (
    PORTUGAL,
    WeeklyEntry,
    leaderboard_already_posted,
    save_leaderboard_post,
)
from app.services.guild_config import GuildConfigService, GuildRuntimeConfig

logger = logging.getLogger(__name__)


async def _weekly_creators_embed_for_guild(
    session_factory: async_sessionmaker[AsyncSession],
    config: GuildRuntimeConfig,
    week_start: date,
) -> tuple[discord.Embed, str, list[int]]:
    async with session_factory() as session:
        rows = await weekly_top_creators_in_anchor_week(
            session,
            discord_guild_id=config.discord_guild_id,
            week_start=week_start,
            limit=10,
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
    embed = build_weekly_creators_embed(week_start, entries, name_for_id)
    content = weekly_creators_mention_content(entries)
    mention_ids = [e.user_id for e in entries]
    return embed, content, mention_ids


async def maybe_post_weekly_creator_leaderboard(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
    *,
    week_start: date,
    configs: list[GuildRuntimeConfig] | None = None,
) -> None:
    if configs is None:
        async with session_factory() as session:
            configs = await guild_config.list_guilds_for_creator_weekly(session)

    for config in configs:
        anchor = config.weekly_leaderboard_anchor
        if anchor is None:
            continue
        channel_id = int(config.announce_channel_id or 0)
        if channel_id <= 0:
            continue

        async with session_factory() as session:
            async with session.begin():
                if await leaderboard_already_posted(session, week_start, channel_id):
                    continue

        channel = bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "canal de anúncios %s inválido para ranking de criadores", channel_id
            )
            continue

        embed, content, mention_ids = await _weekly_creators_embed_for_guild(
            session_factory, config, week_start
        )
        allowed = (
            discord.AllowedMentions(users=[discord.Object(id=uid) for uid in mention_ids])
            if mention_ids
            else discord.AllowedMentions.none()
        )
        message = await channel.send(
            content=content or None,
            embed=embed,
            allowed_mentions=allowed,
        )

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
            "ranking semanal de criadores publicado (%s) no canal %s",
            week_start,
            channel_id,
        )


async def creator_weekly_leaderboard_loop(
    bot: discord.Client,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
) -> None:
    last_post_key: str | None = None
    while True:
        try:
            async with session_factory() as session:
                configs = await guild_config.list_guilds_for_creator_weekly(session)
            if configs:
                now_pt = datetime.now(PORTUGAL)
                for config in configs:
                    anchor = config.weekly_leaderboard_anchor
                    if anchor is None:
                        continue
                    week_start = completed_anchor_week_to_post(now_pt, anchor)
                    if week_start is None:
                        continue
                    key = f"{config.discord_guild_id}-{week_start.isoformat()}-21"
                    if key == last_post_key:
                        continue
                    await maybe_post_weekly_creator_leaderboard(
                        bot,
                        session_factory,
                        guild_config,
                        week_start=week_start,
                        configs=[config],
                    )
                    last_post_key = key
        except Exception:
            logger.exception("ranking semanal de criadores falhou")
        await asyncio.sleep(60)
