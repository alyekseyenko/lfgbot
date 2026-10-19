from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Lobby, LobbyState, User
from app.services.lobbies import get_active_lobby_by_message


@pytest.mark.asyncio
async def test_get_active_lobby_by_message(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    session.add(User(discord_id=1, name="host"))
    lobby = Lobby(
        host_id=1,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        state=LobbyState.open,
        expires_at=now + timedelta(hours=1),
        channel_id=555,
        message_id=999,
        discord_guild_id=100,
    )
    session.add(lobby)
    await session.commit()

    found = await get_active_lobby_by_message(session, channel_id=555, message_id=999)
    assert found is not None
    assert found.id == lobby.id

    missing = await get_active_lobby_by_message(session, channel_id=555, message_id=1)
    assert missing is None
