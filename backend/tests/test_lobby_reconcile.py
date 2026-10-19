from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import EventBus
from app.db.models import User
from app.services.lobbies import close_lobby, create_lobby
from app.services.lobby_reconcile import reconcile_active_lobby_embeds
from app.services.users import upsert_user


@pytest.mark.asyncio
async def test_reconcile_active_lobby_embeds_refreshes_open_only(
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
) -> None:
    refreshed: list[UUID] = []

    async def refresh(lobby_id: UUID) -> None:
        refreshed.append(lobby_id)

    async with session_factory() as session:
        async with session.begin():
            host = await upsert_user(session, 1, "Host")
            open_lobby = await create_lobby(
                session,
                event_bus,
                host=host,
                mode="Unrated",
                slots=2,
                party_code="ABC123",
                expires_in=timedelta(hours=1),
                discord_guild_id=10,
            )
            closed_host = User(discord_id=2, name="h2")
            session.add(closed_host)
            await session.flush()
            closed_lobby = await create_lobby(
                session,
                event_bus,
                host=closed_host,
                mode="Unrated",
                slots=2,
                party_code=None,
                expires_in=timedelta(hours=1),
                discord_guild_id=10,
            )
            await close_lobby(session, event_bus, lobby_id=closed_lobby.id)

    count = await reconcile_active_lobby_embeds(session_factory, refresh=refresh)

    assert count == 1
    assert refreshed == [open_lobby.id]
