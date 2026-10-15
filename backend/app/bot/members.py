from __future__ import annotations

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.discord_roles import extract_from_member
from app.db.models import User
from app.services.users import upsert_user


async def fetch_guild_member(guild: discord.Guild, discord_id: int) -> discord.Member | None:
    cached = guild.get_member(discord_id)
    if cached is not None:
        return cached
    try:
        return await guild.fetch_member(discord_id)
    except discord.HTTPException:
        return None


async def upsert_user_from_member(session: AsyncSession, member: discord.Member) -> User:
    rank, _agent = extract_from_member(member)
    return await upsert_user(session, member.id, str(member), rank=rank)
