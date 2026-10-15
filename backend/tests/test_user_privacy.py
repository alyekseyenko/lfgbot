from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.db.models import LobbyMember, User
from app.services.lobbies import create_lobby, join_lobby
from app.services.lobby_source import LOBBY_SOURCE_SLASH
from app.services.user_privacy import DELETED_USER_DISPLAY_NAME, delete_user_personal_data
from datetime import timedelta

from sqlalchemy import select


@pytest.mark.asyncio
async def test_delete_user_personal_data_anonymizes_and_clears_memberships(
    session: AsyncSession, event_bus: EventBus
) -> None:
    host = User(discord_id=700, name="PlayerOne", rank="Gold")
    guest = User(
        discord_id=701,
        name="Guest",
        rank="Silver",
        riot_game_name="Guest",
        riot_tag="TAG",
    )
    session.add_all([host, guest])
    await session.flush()

    lobby = await create_lobby(
        session,
        event_bus,
        host=host,
        mode="Competitivo",
        slots=2,
        party_code="ABC111",
        expires_in=timedelta(hours=1),
        discord_guild_id=99,
        create_source=LOBBY_SOURCE_SLASH,
    )
    await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest)
    await session.commit()

    async with session.begin():
        result = await delete_user_personal_data(session, guest.discord_id)

    assert result.user_anonymized
    assert result.memberships_removed >= 1

    refreshed = await session.get(User, guest.discord_id)
    assert refreshed is not None
    assert refreshed.name == DELETED_USER_DISPLAY_NAME
    assert refreshed.rank is None
    assert refreshed.riot_game_name is None
    assert refreshed.riot_tag is None
    assert refreshed.player_card_uuid is None

    members = await session.execute(
        select(LobbyMember).where(LobbyMember.user_id == guest.discord_id)
    )
    assert list(members.scalars().all()) == []
