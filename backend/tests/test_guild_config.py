import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.services.guild_config import GuildConfigService


@pytest.fixture
def guild_settings() -> Settings:
    return Settings(
        discord_guild_ids="100,200",
        lfg_channel_ids="10,20",
        gamification_enabled=True,
        stats_channel_id=99,
    )


async def test_channel_allowed_from_db(
    session_factory: async_sessionmaker[AsyncSession],
    guild_settings: Settings,
) -> None:
    service = GuildConfigService(guild_settings)
    async with session_factory() as session:
        async with session.begin():
            await service.upsert_guild(session, discord_guild_id=100, name="Test")
            await service.update_settings(session, 100, lfg_channel_ids=[111, 222])

    assert await service.channel_allowed(session_factory, 100, 111) is True
    assert await service.channel_allowed(session_factory, 100, 999) is False


async def test_ranking_channel_allows_stats_channel(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = GuildConfigService(Settings())
    stats_channel = 42424242
    async with session_factory() as session:
        async with session.begin():
            await service.upsert_guild(session, discord_guild_id=100, name="Test")
            await service.update_settings(
                session,
                100,
                lfg_channel_ids=[111],
                stats_channel_id=stats_channel,
            )

    assert await service.channel_allowed(session_factory, 100, stats_channel) is False
    assert await service.ranking_channel_allowed(session_factory, 100, stats_channel) is True
    assert await service.ranking_channel_allowed(session_factory, 100, 111) is True


async def test_seed_from_env(
    session_factory: async_sessionmaker[AsyncSession],
    guild_settings: Settings,
) -> None:
    service = GuildConfigService(guild_settings)
    async with session_factory() as session:
        async with session.begin():
            await service.seed_from_env(session)

    async with session_factory() as session:
        config = await service.get_config(session, 100)
    assert config.lfg_channel_ids == (10, 20)
    assert config.gamification_enabled is True
    assert config.stats_channel_id == 99


async def test_cache_invalidation_on_patch(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = GuildConfigService(Settings())
    async with session_factory() as session:
        async with session.begin():
            await service.upsert_guild(session, discord_guild_id=1, name="G")
            await service.update_settings(session, 1, lfg_channel_ids=[5])

    async with session_factory() as session:
        first = await service.get_config(session, 1)
    assert first.lfg_channel_ids == (5,)

    async with session_factory() as session:
        async with session.begin():
            await service.update_settings(session, 1, lfg_channel_ids=[6])

    async with session_factory() as session:
        second = await service.get_config(session, 1)
    assert second.lfg_channel_ids == (6,)


async def test_role_mappings_replace(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = GuildConfigService(Settings())
    async with session_factory() as session:
        async with session.begin():
            await service.upsert_guild(session, discord_guild_id=1, name="G")
            await service.replace_role_mappings(
                session,
                1,
                [
                    {
                        "mapping_type": "valorant_rank",
                        "logical_key": "Gold",
                        "discord_role_id": 555,
                    }
                ],
            )

    async with session_factory() as session:
        config = await service.get_config(session, 1)
    assert config.role_mappings[("valorant_rank", "Gold")] == 555
