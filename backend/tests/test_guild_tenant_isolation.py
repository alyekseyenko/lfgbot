from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.events import EventBus
from app.db.models import Lobby, LobbyState, User
from app.services.guild_config import GuildConfigService
from app.services.guild_stats import guild_lobby_stats
from app.services.lobbies import create_lobby


@pytest.mark.asyncio
async def test_guild_stats_exclude_other_guild_lobbies(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    session.add_all(
        [
            User(discord_id=1, name="a"),
            User(discord_id=2, name="b"),
        ]
    )
    session.add_all(
        [
            Lobby(
                host_id=1,
                mode="Competitivo",
                slots=2,
                party_code="AAA111",
                state=LobbyState.open,
                expires_at=now + timedelta(hours=1),
                channel_id=100,
                discord_guild_id=1000,
            ),
            Lobby(
                host_id=2,
                mode="Unrated",
                slots=3,
                party_code="BBB222",
                state=LobbyState.open,
                expires_at=now + timedelta(hours=1),
                channel_id=200,
                discord_guild_id=2000,
            ),
        ]
    )
    await session.commit()

    stats_a = await guild_lobby_stats(
        session,
        discord_guild_id=1000,
        channel_ids=[100],
        days=30,
    )
    stats_b = await guild_lobby_stats(
        session,
        discord_guild_id=2000,
        channel_ids=[200],
        days=30,
    )

    assert stats_a["lobbies_created_period"] == 1
    assert stats_b["lobbies_created_period"] == 1
    assert stats_a["active_lobbies"] == 1
    assert stats_b["active_lobbies"] == 1


@pytest.mark.asyncio
async def test_guild_settings_isolated_per_discord_guild_id(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    service = GuildConfigService(Settings())
    async with session_factory() as session:
        async with session.begin():
            await service.upsert_guild(session, discord_guild_id=501, name="A")
            await service.upsert_guild(session, discord_guild_id=502, name="B")
            await service.update_settings(session, 501, lobby_ttl_minutes=15)
            await service.update_settings(session, 502, lobby_ttl_minutes=60)

    async with session_factory() as session:
        cfg_a = await service.get_config(session, 501)
        cfg_b = await service.get_config(session, 502)

    assert cfg_a.lobby_ttl_minutes == 15
    assert cfg_b.lobby_ttl_minutes == 60


@pytest.mark.asyncio
async def test_active_lobbies_scoped_by_guild_in_stats_not_cross_counted(
    session: AsyncSession,
    event_bus: EventBus,
) -> None:
    host = User(discord_id=9, name="host")
    session.add(host)
    await session.flush()

    async with session.begin():
        await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Competitivo",
            slots=2,
            party_code="XYZ999",
            expires_in=timedelta(hours=2),
            discord_guild_id=77,
            channel_id=7001,
        )
        await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Competitivo",
            slots=2,
            party_code="XYZ998",
            expires_in=timedelta(hours=2),
            discord_guild_id=88,
            channel_id=8001,
        )

    only_77 = await guild_lobby_stats(
        session,
        discord_guild_id=77,
        channel_ids=[7001],
        days=30,
    )
    only_88 = await guild_lobby_stats(
        session,
        discord_guild_id=88,
        channel_ids=[8001],
        days=30,
    )

    assert only_77["lobbies_created_period"] == 1
    assert only_88["lobbies_created_period"] == 1
