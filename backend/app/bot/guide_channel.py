from __future__ import annotations

import logging

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.lfg_panel import resolve_lfg_text_channel
from app.db.models import GuildSettings
from app.services.guide_content import GUIDE_EMBED_TITLE, effective_guide_body
from app.services.lfg_embed_style import DEFAULT_COMPETITIVE_COLOR, parse_embed_hex_color

logger = logging.getLogger(__name__)


def build_guide_embed(body: str, *, color_hex: str = DEFAULT_COMPETITIVE_COLOR) -> discord.Embed:
    color = int(parse_embed_hex_color(color_hex, default=DEFAULT_COMPETITIVE_COLOR), 16)
    return discord.Embed(
        title=GUIDE_EMBED_TITLE,
        description=body,
        color=color,
    )


async def publish_guild_guide(
    bot: commands.Bot,
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    *,
    replace_previous: bool = True,
) -> bool:
    """Publica ou atualiza o guia no canal configurado. Devolve True se houve alteração."""
    async with session_factory() as session:
        result = await session.execute(
            select(GuildSettings).where(GuildSettings.discord_guild_id == guild_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        channel_id = int(row.guide_channel_id or 0)
        if not channel_id:
            return False
        body = effective_guide_body(row.guide_body)
        message_id = int(row.guide_message_id or 0)

    channel = await resolve_lfg_text_channel(bot, channel_id)
    if channel is None:
        logger.warning("guia LFG: canal %s inacessível no servidor %s", channel_id, guild_id)
        return False

    embed = build_guide_embed(body)

    if message_id:
        try:
            msg = await channel.fetch_message(message_id)
            if msg.author.id == bot.user.id:
                await msg.edit(embed=embed)
                return True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    if replace_previous and message_id:
        try:
            old = await channel.fetch_message(message_id)
            if old.author.id == bot.user.id:
                await old.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    message = await channel.send(embed=embed)
    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                select(GuildSettings).where(GuildSettings.discord_guild_id == guild_id)
            )
            settings_row = result.scalar_one_or_none()
            if settings_row is not None:
                settings_row.guide_message_id = message.id
    logger.info("guia LFG publicado no canal %s (servidor %s)", channel_id, guild_id)
    return True


async def ensure_all_guild_guides(
    bot: commands.Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Garante guia nos servidores com canal configurado. Devolve quantos atualizou."""
    updated = 0
    async with session_factory() as session:
        result = await session.execute(
            select(GuildSettings.discord_guild_id).where(GuildSettings.guide_channel_id > 0)
        )
        guild_ids = [int(row[0]) for row in result.all()]

    for guild_id in guild_ids:
        try:
            if await publish_guild_guide(
                bot, session_factory, guild_id, replace_previous=False
            ):
                updated += 1
        except Exception:
            logger.exception("falha ao garantir guia no servidor %s", guild_id)
    return updated
