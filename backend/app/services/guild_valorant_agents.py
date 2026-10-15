from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GuildValorantAgentRole


async def list_guild_agent_role_mappings(
    session: AsyncSession,
    discord_guild_id: int,
) -> list[GuildValorantAgentRole]:
    result = await session.execute(
        select(GuildValorantAgentRole)
        .where(GuildValorantAgentRole.discord_guild_id == discord_guild_id)
        .order_by(GuildValorantAgentRole.agent_uuid.asc())
    )
    return list(result.scalars())


async def replace_guild_agent_role_mappings(
    session: AsyncSession,
    discord_guild_id: int,
    mappings: list[tuple[str, int]],
) -> list[GuildValorantAgentRole]:
    await session.execute(
        delete(GuildValorantAgentRole).where(
            GuildValorantAgentRole.discord_guild_id == discord_guild_id
        )
    )
    for agent_uuid, role_id in mappings:
        session.add(
            GuildValorantAgentRole(
                discord_guild_id=discord_guild_id,
                agent_uuid=agent_uuid,
                discord_role_id=role_id,
            )
        )
    await session.flush()
    return await list_guild_agent_role_mappings(session, discord_guild_id)
