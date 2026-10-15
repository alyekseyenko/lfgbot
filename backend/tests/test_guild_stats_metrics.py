from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.db.models import User
from app.services.guild_stats import guild_lobby_stats
from app.services.lobbies import create_lobby, join_lobby
from app.services.lobby_source import LOBBY_SOURCE_CHAT, LOBBY_SOURCE_SLASH


@pytest.mark.asyncio
async def test_guild_stats_counts_source_and_fill(
    session: AsyncSession, event_bus: EventBus
) -> None:
    guild_id = 5000
    channel_id = 6000
    host = User(discord_id=80, name="h")
    guest = User(discord_id=81, name="g")
    session.add_all([host, guest])
    await session.flush()

    lobby = await create_lobby(
        session,
        event_bus,
        host=host,
        mode="Competitivo",
        slots=1,
        party_code="ZZZ999",
        expires_in=timedelta(hours=2),
        discord_guild_id=guild_id,
        channel_id=channel_id,
        create_source=LOBBY_SOURCE_SLASH,
    )
    await create_lobby(
        session,
        event_bus,
        host=guest,
        mode="Unrated",
        slots=2,
        party_code=None,
        expires_in=timedelta(hours=2),
        discord_guild_id=guild_id,
        channel_id=channel_id,
        create_source=LOBBY_SOURCE_CHAT,
    )
    await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest)
    await session.commit()

    stats = await guild_lobby_stats(
        session,
        discord_guild_id=guild_id,
        channel_ids=[channel_id],
        days=30,
    )
    assert stats["lobbies_created_period"] == 2
    assert stats["created_by_source"]["slash"] == 1
    assert stats["created_by_source"]["chat"] == 1
    assert stats["groups_filled_period"] >= 1
