from __future__ import annotations

import logging

import discord
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.guild_config import GuildConfigService, GuildRuntimeConfig
from app.services.reputation import user_reputation_score

logger = logging.getLogger(__name__)


def reputation_role_targets(
    config: GuildRuntimeConfig, score: int
) -> tuple[bool, bool]:
    want_negative = (
        int(config.reputation_negative_role_id or 0) > 0
        and score <= int(config.reputation_negative_threshold)
    )
    want_positive = (
        int(config.reputation_positive_role_id or 0) > 0
        and score >= int(config.reputation_positive_threshold)
    )
    if want_negative and want_positive:
        if score < 0:
            want_positive = False
        else:
            want_negative = False
    return want_negative, want_positive


async def apply_reputation_roles(
    member: discord.Member,
    config: GuildRuntimeConfig,
    score: int,
) -> None:
    want_negative, want_positive = reputation_role_targets(config, score)
    neg_id = int(config.reputation_negative_role_id or 0)
    pos_id = int(config.reputation_positive_role_id or 0)

    to_add: list[discord.Role] = []
    to_remove: list[discord.Role] = []

    for role_id, want in ((neg_id, want_negative), (pos_id, want_positive)):
        if role_id <= 0:
            continue
        role = member.guild.get_role(role_id)
        if role is None:
            logger.warning("role de reputação %s não encontrada em %s", role_id, member.guild.id)
            continue
        if want and role not in member.roles:
            to_add.append(role)
        elif not want and role in member.roles:
            to_remove.append(role)

    if to_remove:
        await member.remove_roles(*to_remove, reason="Reputação LFG")
    if to_add:
        await member.add_roles(*to_add, reason="Reputação LFG")


async def sync_member_reputation_roles(
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
    member: discord.Member,
) -> None:
    guild_id = member.guild.id
    async with session_factory() as session:
        config = await guild_config.get_config(session, guild_id)
        score = await user_reputation_score(
            session, discord_guild_id=guild_id, user_id=member.id
        )
    await apply_reputation_roles(member, config, score)


async def sync_reputation_roles_for_users(
    bot: discord.Client,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
    guild_id: int,
    user_ids: list[int],
) -> None:
    guild = bot.get_guild(guild_id)
    if guild is None:
        return
    unique = sorted({int(uid) for uid in user_ids})
    if not unique:
        return
    async with session_factory() as session:
        config = await guild_config.get_config(session, guild_id)
        scores = {
            uid: await user_reputation_score(
                session, discord_guild_id=guild_id, user_id=uid
            )
            for uid in unique
        }
    for uid in unique:
        member = guild.get_member(uid)
        if member is None:
            continue
        try:
            await apply_reputation_roles(member, config, scores[uid])
        except discord.Forbidden:
            logger.warning("sem permissão para roles de reputação em %s", uid)
        except discord.HTTPException:
            logger.exception("falha ao sincronizar roles de reputação para %s", uid)
