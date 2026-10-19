from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import discord
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.embeds import allowed_mentions_for_lobby, build_lobby_embed
from app.bot.lfg_panel import notify_panel_sticky_after_lobby
from app.bot.members import fetch_guild_member, upsert_user_from_member
from app.bot.views import make_lobby_view
from app.services.lobby_post_style import normalize_post_style
from app.core.config import Settings
from app.core.events import EventBus
from app.services import lobbies as lobby_service
from app.bot.party_code_config import party_code_max_length_from_runtime
from app.services.guild_config import GuildConfigService
from app.services.party_code import DEFAULT_PARTY_CODE_MAX_LENGTH
from app.services.lfg_embed_style import lobby_embed_style_for_post


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
    guild_config: GuildConfigService | None = None,
    create_source: str = "unknown",
    post_style: str = "simple",
) -> discord.Message:
    ttl_minutes = settings.lobby_ttl_minutes
    party_code_max_length = DEFAULT_PARTY_CODE_MAX_LENGTH
    runtime = None
    if guild_config is not None and isinstance(channel, discord.abc.GuildChannel):
        runtime = await guild_config.get_config_for_factory(
            session_factory, channel.guild.id
        )
        ttl_minutes = runtime.lobby_ttl_minutes
        party_code_max_length = party_code_max_length_from_runtime(runtime)
    expires_in = timedelta(minutes=ttl_minutes)
    discord_guild_id: int | None = None
    if isinstance(channel, discord.abc.GuildChannel):
        discord_guild_id = channel.guild.id

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
                discord_guild_id=discord_guild_id,
                create_source=create_source,
                post_style=normalize_post_style(post_style),
                party_code_max_length=party_code_max_length,
            )

    lobby_detail = await _load_lobby(session_factory, lobby.id)
    guild = channel.guild if isinstance(channel, discord.abc.GuildChannel) else None
    thumb = settings.embed_thumbnail_url.strip() or None
    role_mappings: dict[tuple[str, str], int] | None = None
    embed_style = None
    if guild_config is not None and guild is not None:
        cfg = await guild_config.get_config_for_factory(session_factory, guild.id)
        role_mappings = cfg.role_mappings
        embed_style = lobby_embed_style_for_post(cfg, lobby_detail.post_style)
    host_member = None
    if guild is not None:
        host_member = await fetch_guild_member(guild, host.id)
    built = build_lobby_embed(
        lobby_detail,
        guild=guild,
        thumbnail_url=thumb,
        role_mappings=role_mappings,
        embed_style=embed_style,
        host_member=host_member,
    )
    style = normalize_post_style(post_style)
    show_close_button = True
    show_edit_button = True
    if embed_style is not None:
        show_close_button = embed_style.visibility.show_close_button
        show_edit_button = embed_style.visibility.show_edit_button
    view = make_lobby_view(
        lobby.id,
        style,
        show_close_button=show_close_button,
        show_edit_button=show_edit_button,
    )
    view.bind(session_factory, event_bus, guild_config)
    view.refresh_buttons("open", slots)

    message = await channel.send(
        content=built.content or None,
        embed=built.embed,
        view=view,
        reference=reference,
        allowed_mentions=allowed_mentions_for_lobby(built),
        silent=True,
    )

    async with session_factory() as session:
        async with session.begin():
            await lobby_service.set_lobby_message(session, lobby.id, message.channel.id, message.id)

    bot.add_view(view)

    if isinstance(channel, discord.TextChannel):
        await notify_panel_sticky_after_lobby(
            bot, settings, session_factory, event_bus, channel, guild_config
        )

    return message


async def _load_lobby(session_factory: async_sessionmaker[AsyncSession], lobby_id: UUID):
    async with session_factory() as session:
        return await lobby_service.get_lobby_detail(session, lobby_id)
