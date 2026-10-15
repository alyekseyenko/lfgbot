from __future__ import annotations

import logging
from uuid import UUID

import discord
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.events import DomainEvent, EventBus, EventType
from app.db.models import User
from app.services.gamification import (
    ROLE_AGENTE,
    ROLE_RADIANTE,
    ROLE_RECRUTA,
    profile_stats,
    role_name_for_level,
)
from app.services.lobbies import get_lobby_detail

logger = logging.getLogger(__name__)

_LFG_ROLE_NAMES = (ROLE_RADIANTE, ROLE_AGENTE, ROLE_RECRUTA)


async def apply_lfg_roles(member: discord.Member, level: str) -> None:
    guild = member.guild
    roles_by_name = {role.name: role for role in guild.roles}
    target_name = role_name_for_level(level)

    to_remove = [
        roles_by_name[name]
        for name in _LFG_ROLE_NAMES
        if name in roles_by_name and roles_by_name[name] in member.roles
    ]
    if to_remove:
        await member.remove_roles(*to_remove, reason="Sincronização nível LFG")

    if target_name is None or target_name not in roles_by_name:
        if target_name:
            logger.warning("role %s não encontrada em %s", target_name, guild.id)
        return

    role = roles_by_name[target_name]
    if role not in member.roles:
        await member.add_roles(role, reason="Sincronização nível LFG")


async def sync_member_lfg_roles(
    session_factory: async_sessionmaker[AsyncSession],
    member: discord.Member,
) -> None:
    async with session_factory() as session:
        stats = await profile_stats(session, member.id)
    await apply_lfg_roles(member, stats.level)


async def sync_awarded_users_for_lobby(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    lobby_id: UUID,
    user_ids: list[int],
) -> None:
    if not user_ids:
        return

    async with session_factory() as session:
        try:
            lobby = await get_lobby_detail(session, lobby_id)
        except Exception:
            logger.exception("gamification: lobby %s not found for role sync", lobby_id)
            return

    if lobby.channel_id is None:
        return

    channel = bot.get_channel(lobby.channel_id)
    if not isinstance(channel, discord.abc.GuildChannel):
        return

    guild = channel.guild
    for discord_id in user_ids:
        member = guild.get_member(discord_id)
        if member is None:
            continue
        try:
            await sync_member_lfg_roles(session_factory, member)
        except discord.Forbidden:
            logger.warning("sem permissão para roles LFG em %s (user %s)", guild.id, discord_id)
        except discord.HTTPException:
            logger.exception("falha ao sincronizar roles para %s", discord_id)


def attach_gamification_listener(
    bot: discord.Client,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
) -> None:
    if not settings.gamification_enabled:
        return

    async def _on_domain_event(event: DomainEvent) -> None:
        if event.type not in (EventType.lobby_closed, EventType.lobby_expired):
            return
        payload = event.payload or {}
        raw_ids = payload.get("awarded_user_ids")
        if not isinstance(raw_ids, list):
            return
        user_ids = [int(x) for x in raw_ids]
        await sync_awarded_users_for_lobby(bot, session_factory, event.lobby_id, user_ids)

    event_bus.subscribe(_on_domain_event)


async def resolve_display_name(
    session_factory: async_sessionmaker[AsyncSession], user_id: int
) -> str:
    async with session_factory() as session:
        result = await session.execute(select(User.name).where(User.discord_id == user_id))
        name = result.scalar_one_or_none()
    return name or str(user_id)
