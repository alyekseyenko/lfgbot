from __future__ import annotations

import logging
from datetime import timedelta

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.members import fetch_guild_member
from app.services.guild_config import GuildConfigService
from app.services.host_recreate_cooldown import DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS
from app.services.lfg_embed_style import member_has_immune_role

logger = logging.getLogger(__name__)


async def resolve_host_recreate_cooldown(
    guild_config: GuildConfigService | None,
    session_factory: async_sessionmaker[AsyncSession],
    host: discord.Member,
    channel: discord.abc.Messageable,
) -> timedelta:
    if not isinstance(channel, discord.abc.GuildChannel):
        return timedelta(seconds=DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS)
    if guild_config is None:
        logger.warning(
            "host recreate cooldown sem guild_config (guild=%s host=%s) — usa %ss",
            channel.guild.id,
            host.id,
            DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS,
        )
        return timedelta(seconds=DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS)

    member = await fetch_guild_member(channel.guild, host.id) or host
    cfg = await guild_config.get_config_for_factory(session_factory, channel.guild.id)
    duration = cfg.host_recreate_cooldown_for_member(member)
    if member_has_immune_role(member, cfg.immune_role_ids):
        logger.debug(
            "host recreate cooldown isento %ss (host=%s guild=%s)",
            duration.total_seconds(),
            host.id,
            channel.guild.id,
        )
    return duration
