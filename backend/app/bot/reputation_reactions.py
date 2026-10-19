from __future__ import annotations

import logging

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.guild_audit_log import send_guild_audit_log
from app.db.models import Lobby
from app.bot.reputation_roles import sync_reputation_roles_for_users
from app.services.reputation import (
    REACTION_THUMBS_DOWN,
    REACTION_THUMBS_UP,
    apply_vote,
    clear_vote,
    get_reputation_post_by_message,
    lobby_participant_ids,
    partial_emoji_value,
)

logger = logging.getLogger(__name__)


def attach_reputation_reaction_handlers(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config,
) -> None:
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id is None or bot.user and payload.user_id == bot.user.id:
            return
        value = partial_emoji_value(payload.emoji)
        if value is None:
            return
        await _handle_vote(
            bot,
            session_factory,
            guild_config,
            channel_id=payload.channel_id,
            message_id=payload.message_id,
            voter_id=payload.user_id,
            value=value,
            remove_on_reject=True,
        )

    async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id is None:
            return
        value = partial_emoji_value(payload.emoji)
        if value is None:
            return
        guild_id = 0
        participant_ids: list[int] = []
        async with session_factory() as session:
            async with session.begin():
                post = await get_reputation_post_by_message(
                    session, payload.channel_id, payload.message_id
                )
                if post is None:
                    return
                lobby = await session.get(Lobby, post.lobby_id)
                if lobby is not None:
                    guild_id = int(lobby.discord_guild_id or 0)
                    participant_ids = await lobby_participant_ids(session, post.lobby_id)
                await clear_vote(session, lobby_id=post.lobby_id, voter_id=payload.user_id)
        if guild_id > 0 and participant_ids:
            await sync_reputation_roles_for_users(
                bot,
                session_factory,
                guild_config,
                guild_id,
                participant_ids,
            )

    bot.add_listener(on_raw_reaction_add, "on_raw_reaction_add")
    bot.add_listener(on_raw_reaction_remove, "on_raw_reaction_remove")


async def _handle_vote(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config,
    *,
    channel_id: int,
    message_id: int,
    voter_id: int,
    value: int,
    remove_on_reject: bool,
) -> None:
    participant_ids: list[int] = []
    async with session_factory() as session:
        async with session.begin():
            post = await get_reputation_post_by_message(session, channel_id, message_id)
            if post is None:
                return
            lobby = await session.get(Lobby, post.lobby_id)
            if lobby is None:
                return
            result = await apply_vote(
                session, lobby_id=post.lobby_id, voter_id=voter_id, value=value
            )
            guild_id = int(lobby.discord_guild_id or 0)
            host_id = int(lobby.host_id)
            mode = lobby.mode
            party_code = (lobby.party_code or "").strip() or "—"
            if result.accepted:
                participant_ids = await lobby_participant_ids(session, post.lobby_id)

    if not result.accepted and remove_on_reject and result.reason == "cap_reached":
        channel = bot.get_channel(channel_id)
        if isinstance(channel, discord.TextChannel):
            try:
                message = await channel.fetch_message(message_id)
                await message.remove_reaction(
                    REACTION_THUMBS_UP if value > 0 else REACTION_THUMBS_DOWN,
                    discord.Object(id=voter_id),
                )
            except discord.HTTPException:
                logger.warning("não foi possível remover reação extra em %s", message_id)
        return

    if not result.accepted:
        return

    label = "👍" if value > 0 else "👎"
    if guild_id > 0:
        await send_guild_audit_log(
            bot,
            guild_config,
            session_factory,
            guild_id,
            title="Reputação",
            description=(
                f"<@{voter_id}> reagiu {label} ao grupo de <@{host_id}> "
                f"(**{mode}**, party `{party_code}`)."
            ),
            colour=discord.Colour.green() if value > 0 else discord.Colour.red(),
        )
        if participant_ids:
            await sync_reputation_roles_for_users(
                bot,
                session_factory,
                guild_config,
                guild_id,
                participant_ids,
            )
