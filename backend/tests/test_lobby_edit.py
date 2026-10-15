from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.db.models import LobbyState
from app.services.errors import LobbyEditError
from app.services.lobbies import create_lobby, get_lobby_detail, join_lobby, update_lobby_as_host
from app.services.lobby_patch import LobbyHostPatch
from app.services.users import upsert_user


@pytest.mark.asyncio
async def test_host_updates_rank_range(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 1001, "Host", rank="Gold")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 1001, "Host", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code="ABC123",
            min_rank="Gold",
            expires_in=timedelta(minutes=30),
        )

    patch = LobbyHostPatch(min_rank="Silver", max_rank="Diamond")
    async with session.begin():
        updated = await update_lobby_as_host(
            session,
            event_bus,
            lobby_id=lobby.id,
            host_id=1001,
            patch=patch,
        )
    assert updated.min_rank == "Silver"
    assert updated.max_rank == "Diamond"


@pytest.mark.asyncio
async def test_cannot_reduce_slots_below_members(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 1002, "Host", rank="Gold")
    await upsert_user(session, 1003, "P1", rank="Gold")
    await upsert_user(session, 1006, "P2", rank="Gold")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 1002, "Host", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )
        guest1 = await upsert_user(session, 1003, "P1", rank="Gold")
        guest2 = await upsert_user(session, 1006, "P2", rank="Gold")
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest1)
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest2)

    async with session.begin():
        with pytest.raises(LobbyEditError):
            await update_lobby_as_host(
                session,
                event_bus,
                lobby_id=lobby.id,
                host_id=1002,
                patch=LobbyHostPatch(slots=1),
            )


@pytest.mark.asyncio
async def test_increasing_slots_reopens_full_lobby(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 1004, "Host", rank="Gold")
    await upsert_user(session, 1005, "P1", rank="Gold")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 1004, "Host", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=1,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )
        guest = await upsert_user(session, 1005, "P1", rank="Gold")
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest)

    async with session.begin():
        before = await get_lobby_detail(session, lobby.id)
    assert before.state == LobbyState.full

    async with session.begin():
        updated = await update_lobby_as_host(
            session,
            event_bus,
            lobby_id=lobby.id,
            host_id=1004,
            patch=LobbyHostPatch(slots=3),
        )
    assert updated.state == LobbyState.open
    assert updated.slots == 3
