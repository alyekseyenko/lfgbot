from __future__ import annotations

import logging

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.guild_audit_log import send_guild_audit_log
from app.bot.ranking_embed import build_creator_level_up_embed
from app.core.events import DomainEvent, EventBus, EventType
from app.services.creator_levels import (
    count_rooms_created,
    creator_role_ids_for_levels,
    did_creator_level_up,
    ensure_default_creator_levels,
)
from app.services.guild_config import GuildConfigService
from app.services.lobbies import get_lobby_detail

logger = logging.getLogger(__name__)


async def apply_creator_level_roles(
    member: discord.Member,
    levels: list,
    *,
    current_level_number: int,
) -> None:
    guild = member.guild
    mapped_ids = creator_role_ids_for_levels(levels)
    current_role_id: int | None = None
    for item in levels:
        if item.level_number == current_level_number and item.discord_role_id:
            current_role_id = item.discord_role_id
            break

    to_remove: list[discord.Role] = []
    for role_id in mapped_ids:
        if current_role_id is not None and role_id == current_role_id:
            continue
        role = guild.get_role(role_id)
        if role is not None and role in member.roles:
            to_remove.append(role)
    if to_remove:
        await member.remove_roles(*to_remove, reason="Nível de criador atualizado")

    if current_role_id is None:
        return
    role = guild.get_role(current_role_id)
    if role is None:
        logger.warning(
            "role de criador %s não encontrada em %s", current_role_id, guild.id
        )
        return
    if role not in member.roles:
        await member.add_roles(role, reason="Subida de nível de criador")


async def send_creator_level_up_announcement(
    bot: discord.Client,
    *,
    channel_id: int,
    host_id: int,
    level_name: str,
    level_number: int,
    rooms_created: int,
) -> None:
    channel = bot.get_channel(channel_id)
    if not isinstance(channel, discord.TextChannel):
        logger.warning("canal de anúncios %s inválido ou inacessível", channel_id)
        return
    embed = build_creator_level_up_embed(
        level_name=level_name,
        level_number=level_number,
        rooms_created=rooms_created,
    )
    await channel.send(
        content=f"<@{host_id}>",
        embed=embed,
        allowed_mentions=discord.AllowedMentions(users=[discord.Object(id=host_id)]),
    )


async def handle_creator_level_on_lobby_created(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
    event: DomainEvent,
) -> None:
    try:
        async with session_factory() as session:
            lobby = await get_lobby_detail(session, event.lobby_id)
    except Exception:
        logger.exception("criador: lobby %s não encontrado", event.lobby_id)
        return

    guild_id = int(lobby.discord_guild_id or 0)
    if guild_id <= 0:
        return

    host_id = int(lobby.host_id)
    async with session_factory() as session:
        levels = await ensure_default_creator_levels(session, guild_id)
        count_after = await count_rooms_created(
            session, host_id, discord_guild_id=guild_id
        )
    count_before = max(0, count_after - 1)
    leveled_up, after_progress, _before = did_creator_level_up(
        count_before, count_after, levels
    )
    if not leveled_up or after_progress.current is None:
        return

    guild = bot.get_guild(guild_id)
    if guild is None:
        return
    member = guild.get_member(host_id)
    if member is not None:
        try:
            await apply_creator_level_roles(
                member,
                levels,
                current_level_number=after_progress.current.level_number,
            )
        except discord.Forbidden:
            logger.warning(
                "sem permissão para roles de criador em %s (user %s)", guild_id, host_id
            )
            await send_guild_audit_log(
                bot,
                guild_config,
                session_factory,
                guild_id,
                title="Roles de criador",
                description=(
                    f"Não foi possível atribuir cargos a <@{host_id}> "
                    f"(nível **{after_progress.current.name}**). "
                    "Confirma que o bot está **acima** das roles e tem **Gerir cargos**."
                ),
                colour=discord.Colour.orange(),
            )
        except discord.HTTPException:
            logger.exception("falha ao atribuir roles de criador para %s", host_id)

    async with session_factory() as session:
        config = await guild_config.get_config(session, guild_id)
    channel_id = int(config.announce_channel_id or 0)
    if channel_id <= 0:
        return

    try:
        await send_creator_level_up_announcement(
            bot,
            channel_id=channel_id,
            host_id=host_id,
            level_name=after_progress.current.name,
            level_number=after_progress.current.level_number,
            rooms_created=after_progress.rooms_created,
        )
    except discord.Forbidden:
        logger.warning("sem permissão para anunciar nível em %s", channel_id)
    except discord.HTTPException:
        logger.exception("falha ao anunciar subida de nível para %s", host_id)


def attach_creator_level_listener(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> None:
    async def _on_domain_event(event: DomainEvent) -> None:
        if event.type != EventType.lobby_created:
            return
        await handle_creator_level_on_lobby_created(
            bot, session_factory, guild_config, event
        )

    event_bus.subscribe(_on_domain_event)
