from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.services.guild_config import GuildConfigService, GuildRuntimeConfig
from app.services.party_code import (
    DEFAULT_PARTY_CODE_MAX_LENGTH,
    clamp_party_code_max_length,
)


def party_code_max_length_from_runtime(runtime: GuildRuntimeConfig | None) -> int:
    if runtime is None:
        return DEFAULT_PARTY_CODE_MAX_LENGTH
    return clamp_party_code_max_length(runtime.party_code_max_length)


async def resolve_party_code_max_length(
    guild_config: GuildConfigService | None,
    session_factory: async_sessionmaker,
    guild_id: int | None,
) -> int:
    if guild_config is None or guild_id is None:
        return DEFAULT_PARTY_CODE_MAX_LENGTH
    runtime = await guild_config.get_config_for_factory(session_factory, guild_id)
    return party_code_max_length_from_runtime(runtime)
