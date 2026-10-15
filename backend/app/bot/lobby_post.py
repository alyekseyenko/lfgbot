from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.embeds import allowed_mentions_for_roles, build_lobby_embed
from app.bot.lfg_panel import notify_panel_sticky_after_lobby
from app.bot.views import LobbyView
from app.core.config import Settings
from app.core.events import EventBus
from app.services import lobbies as lobby_service
from app.bot.members import upsert_user_from_member


async def publish_lobby(
    bot: commands.Bot,
    channel: discord.abc.Messageable,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    *,
    host: discord.Member,
    mode: str,
    slots: int,
    party_code: str | None,
    min_rank: str | None = None,
    max_rank: str | None = None,
    party_code_public: bool = True,
    wanted_agents: list[str] | None = None,
    ranks_verified: bool = False,
    reference: discord.Message | None = None,
) -> discord.Message:
    expires_in = timedelta(minutes=settings.lobby_ttl_minutes)

    async with session_factory() as session:
        async with session.begin():
            user = await upsert_user_from_member(session, host)
            lobby = await lobby_service.create_lobby(
                session,
                event_bus,
                host=user,
                mode=mode,
                slots=slots,
                party_code=party_code,
                min_rank=min_rank,
                max_rank=max_rank,
                party_code_public=party_code_public,
                wanted_agents=wanted_agents,
                ranks_verified=ranks_verified,
                expires_in=expires_in,
            )

    lobby_detail = await _load_lobby(session_factory, lobby.id)
    guild = channel.guild if isinstance(channel, discord.abc.GuildChannel) else None
    thumb = settings.embed_thumbnail_url.strip() or None
    built = build_lobby_embed(lobby_detail, guild=guild, thumbnail_url=thumb)
    view = LobbyView(lobby.id)
    view.bind(session_factory, event_bus)
    view.refresh_buttons("open", slots)

    message = await channel.send(
        embed=built.embed,
        view=view,
        reference=reference,
        allowed_mentions=allowed_mentions_for_roles(built.mention_role_ids),
    )

    async with session_factory() as session:
        async with session.begin():
            await lobby_service.set_lobby_message(session, lobby.id, message.channel.id, message.id)

    bot.add_view(view)

    if isinstance(channel, discord.TextChannel):
        await notify_panel_sticky_after_lobby(
            bot, settings, session_factory, event_bus, channel
        )

    return message


async def _load_lobby(session_factory: async_sessionmaker[AsyncSession], lobby_id: UUID):
    async with session_factory() as session:
        return await lobby_service.get_lobby_detail(session, lobby_id)
