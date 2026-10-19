from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lobby, LobbyMember, LobbyState, User
from app.services.guild_stats import guild_lobby_stats_lifetime


@pytest.mark.asyncio
async def test_lifetime_includes_legacy_offsets(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    session.add(User(discord_id=1, name="a"))
    session.add(User(discord_id=2, name="b"))
    lobby = Lobby(
        host_id=1,
        mode="Competitivo",
        slots=2,
        party_code="ABC001",
        state=LobbyState.open,
        expires_at=now + timedelta(hours=1),
        channel_id=99,
        discord_guild_id=100,
    )
    session.add(lobby)
    await session.flush()
    session.add(
        LobbyMember(
            lobby_id=lobby.id,
            user_id=2,
            joined_at=now,
        )
    )
    await session.commit()

    stats = await guild_lobby_stats_lifetime(
        session,
        discord_guild_id=100,
        channel_ids=[99],
        legacy_lobbies=10,
        legacy_joins=30,
        legacy_users=5,
    )

    assert stats["lobbies_created_bot"] == 1
    assert stats["joins_bot"] == 1
    assert stats["users_bot"] == 2
    assert stats["lobbies_created_lifetime"] == 11
    assert stats["joins_lifetime"] == 31
    assert stats["users_lifetime"] == 7
