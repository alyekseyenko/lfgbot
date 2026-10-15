from __future__ import annotations

from datetime import timedelta

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.guild_config import GuildConfigService
from app.services.host_recreate_cooldown import DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS


async def resolve_host_recreate_cooldown(
    guild_config: GuildConfigService | None,
    session_factory: async_sessionmaker[AsyncSession],
    host: discord.Member,
    channel: discord.abc.Messageable,
) -> timedelta:
    if guild_config is not None and isinstance(channel, discord.abc.GuildChannel):
        cfg = await guild_config.get_config_for_factory(session_factory, channel.guild.id)
        return cfg.host_recreate_cooldown_for_member(host)
    return timedelta(seconds=DEFAULT_HOST_RECREATE_COOLDOWN_SECONDS)
