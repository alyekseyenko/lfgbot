"""Auditoria para staff: embeds num canal Discord configurado por guild.

Não existe tabela de audit log na PostgreSQL — só guardamos ``log_channel_id`` em
``guild_settings``. O histórico fica no Discord (e desaparece se apagarem mensagens).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import DomainEvent, EventBus, EventType
from app.services.errors import LobbyNotFoundError
from app.services.guild_config import GuildConfigService
from app.services.lobbies import get_lobby_detail
from app.services.lobby_source import (
    LOBBY_SOURCE_CHAT,
    LOBBY_SOURCE_PANEL,
    LOBBY_SOURCE_SLASH,
    LOBBY_SOURCE_UNKNOWN,
)

logger = logging.getLogger(__name__)

_SOURCE_LABELS = {
    LOBBY_SOURCE_SLASH: "/procurar",
    LOBBY_SOURCE_PANEL: "painel",
    LOBBY_SOURCE_CHAT: "chat automático",
    LOBBY_SOURCE_UNKNOWN: "desconhecida",
}

_AUDIT_EVENT_TYPES = frozenset(
    {
        EventType.lobby_created,
        EventType.lobby_closed,
        EventType.lobby_expired,
        EventType.member_left,
    }
)


async def send_guild_audit_log(
    bot: discord.Client,
    guild_config: GuildConfigService,
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int,
    *,
    title: str,
    description: str,
    colour: discord.Colour | None = None,
    fields: Iterable[tuple[str, str, bool]] | None = None,
    footer: str | None = None,
) -> None:
    if guild_id <= 0:
        return
    try:
        config = await guild_config.get_config_for_factory(session_factory, guild_id)
    except Exception:
        logger.exception("audit log: failed to load guild config %s", guild_id)
        return
    channel_id = int(config.log_channel_id or 0)
    if channel_id <= 0:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except discord.HTTPException:
            logger.warning("audit log: channel %s not found in guild %s", channel_id, guild_id)
            return
    if not isinstance(channel, discord.TextChannel):
        return

    embed = discord.Embed(
        title=title[:256],
        description=description[:4096],
        colour=colour or discord.Colour.blurple(),
        timestamp=datetime.now(UTC),
    )
    if fields:
        for name, value, inline in fields:
            if value.strip():
                embed.add_field(name=name[:256], value=value[:1024], inline=inline)
    if footer:
        embed.set_footer(text=footer[:2048])
    try:
        await channel.send(embed=embed)
    except discord.HTTPException:
        logger.exception("audit log: failed to send to channel %s", channel_id)


def _resolve_guild_id(
    bot: discord.Client, lobby_guild_id: int | None, channel_id: int | None
) -> int | None:
    if lobby_guild_id is not None and lobby_guild_id > 0:
        return int(lobby_guild_id)
    if channel_id is None:
        return None
    ch = bot.get_channel(channel_id)
    if isinstance(ch, discord.abc.GuildChannel):
        return ch.guild.id
    return None


def _format_lobby_created(lobby) -> str:
    source = _SOURCE_LABELS.get(lobby.create_source or "", lobby.create_source or "?")
    host = f"<@{lobby.host_id}>"
    channel = f"<#{lobby.channel_id}>" if lobby.channel_id else "—"
    code = lobby.party_code or "sem código"
    return (
        f"**Host:** {host}\n"
        f"**Canal:** {channel}\n"
        f"**Modo:** {lobby.mode} · **Vagas:** {lobby.slots}\n"
        f"**Código:** `{code}` · **Origem:** {source}"
    )


def attach_guild_audit_listener(
    bot: commands.Bot,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> None:
    async def on_domain_event(event: DomainEvent) -> None:
        if event.type not in _AUDIT_EVENT_TYPES:
            return
        if event.type == EventType.member_left:
            reason = (event.payload or {}).get("reason")
            if reason != "kicked":
                return
        await _deliver_domain_audit_event(bot, session_factory, guild_config, event)

    event_bus.subscribe(on_domain_event)


async def _deliver_domain_audit_event(
    bot: commands.Bot,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
    event: DomainEvent,
) -> None:
    try:
        async with session_factory() as session:
            lobby = await get_lobby_detail(session, event.lobby_id)
    except LobbyNotFoundError:
        logger.warning(
            "audit log: lobby %s not found (%s)",
            event.lobby_id,
            event.type.value,
        )
        return

    try:
        guild_id = _resolve_guild_id(bot, lobby.discord_guild_id, lobby.channel_id)
        if guild_id is None:
            logger.warning("audit log: could not resolve guild for lobby %s", event.lobby_id)
            return

        if event.type == EventType.lobby_created:
            await send_guild_audit_log(
                bot,
                guild_config,
                session_factory,
                guild_id,
                title="Pedido LFG criado",
                description=_format_lobby_created(lobby),
                colour=discord.Colour.green(),
            )
            return

        if event.type == EventType.lobby_closed:
            await send_guild_audit_log(
                bot,
                guild_config,
                session_factory,
                guild_id,
                title="Pedido LFG fechado",
                description=f"**Host:** <@{lobby.host_id}>\n**Modo:** {lobby.mode}",
                colour=discord.Colour.light_grey(),
            )
            return

        if event.type == EventType.lobby_expired:
            await send_guild_audit_log(
                bot,
                guild_config,
                session_factory,
                guild_id,
                title="Pedido LFG expirado",
                description=f"**Host:** <@{lobby.host_id}>\n**Modo:** {lobby.mode}",
                colour=discord.Colour.orange(),
            )
            return

        if event.type == EventType.member_left:
            user_id = (event.payload or {}).get("user_id")
            await send_guild_audit_log(
                bot,
                guild_config,
                session_factory,
                guild_id,
                title="Jogador expulso do pedido",
                description=(
                    f"**Host:** <@{lobby.host_id}>\n"
                    f"**Jogador:** <@{user_id}>\n"
                    f"**Lobby:** `{lobby.id}`"
                ),
                colour=discord.Colour.red(),
            )
    except Exception:
        logger.exception(
            "audit log: failed to deliver event %s for lobby %s",
            event.type.value,
            event.lobby_id,
        )
