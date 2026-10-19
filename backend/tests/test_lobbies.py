import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.events import EventBus
from app.db.models import LobbyState
from app.services.errors import LobbyFullError, LobbyNotJoinableError, NotInLobbyError
from app.services.lobbies import (
    close_lobby,
    close_lobby_as_host,
    create_lobby,
    expire_due_lobbies,
    get_host_active_lobby,
    get_lobby_detail,
    join_lobby,
    leave_lobby,
)
from app.services.users import upsert_user


async def _host(session: AsyncSession, discord_id: int = 1001) -> None:
    await upsert_user(session, discord_id, f"Host{discord_id}")


@pytest.mark.asyncio
async def test_join_twice_is_idempotent(session: AsyncSession, event_bus: EventBus) -> None:
    await _host(session, 1)
    user = await upsert_user(session, 2, "Player2")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 1, "Host1")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code="ABC001",
            min_rank=None,
            expires_in=timedelta(minutes=30),
        )

    async with session.begin():
        host = await upsert_user(session, 1, "Host1")
        user = await upsert_user(session, 2, "Player2")
        m1 = await join_lobby(session, event_bus, lobby_id=lobby.id, user=user)
        m2 = await join_lobby(session, event_bus, lobby_id=lobby.id, user=user)
    assert m1.id == m2.id


@pytest.mark.asyncio
async def test_lobby_full_rejects_extra_player(session: AsyncSession, event_bus: EventBus) -> None:
    await _host(session, 10)
    await upsert_user(session, 11, "P11")
    await upsert_user(session, 12, "P12")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 10, "Host10")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=1,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )

    async with session.begin():
        u11 = await upsert_user(session, 11, "P11")
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=u11)

    async with session.begin():
        u12 = await upsert_user(session, 12, "P12")
        with pytest.raises(LobbyFullError):
            await join_lobby(session, event_bus, lobby_id=lobby.id, user=u12)


@pytest.mark.asyncio
async def test_leave_reopens_full_lobby(session: AsyncSession, event_bus: EventBus) -> None:
    await _host(session, 20)
    await upsert_user(session, 21, "P21")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 20, "Host20")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=1,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )
        u21 = await upsert_user(session, 21, "P21")
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=u21)

    async with session.begin():
        u21 = await upsert_user(session, 21, "P21")
        await leave_lobby(session, event_bus, lobby_id=lobby.id, user=u21, reason="left")

    async with session.begin():
        from app.services.lobbies import get_lobby_detail

        refreshed = await get_lobby_detail(session, lobby.id)
    assert refreshed.state == LobbyState.open


@pytest.mark.asyncio
async def test_expire_due_lobbies(session: AsyncSession, event_bus: EventBus) -> None:
    await _host(session, 30)
    await session.commit()
    past = datetime.now(UTC) - timedelta(minutes=1)

    async with session.begin():
        host = await upsert_user(session, 30, "Host30")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(minutes=-5),
        )
        lobby.expires_at = past

    async with session.begin():
        expired = await expire_due_lobbies(session, event_bus, now=datetime.now(UTC))

    assert len(expired) == 1
    assert expired[0].state == LobbyState.expired


@pytest.mark.asyncio
async def test_leave_when_not_member_raises(session: AsyncSession, event_bus: EventBus) -> None:
    await _host(session, 40)
    await upsert_user(session, 41, "P41")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 40, "Host40")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )

    async with session.begin():
        u41 = await upsert_user(session, 41, "P41")
        with pytest.raises(NotInLobbyError):
            await leave_lobby(session, event_bus, lobby_id=lobby.id, user=u41, reason="left")


@pytest.mark.asyncio
async def test_concurrent_join_one_slot(
    session_factory: async_sessionmaker[AsyncSession], event_bus: EventBus
) -> None:
    async with session_factory() as session:
        await _host(session, 50)
        await upsert_user(session, 51, "P51")
        await upsert_user(session, 52, "P52")
        await session.commit()

    async with session_factory() as session:
        async with session.begin():
            host = await upsert_user(session, 50, "Host50")
            lobby = await create_lobby(
                session,
                event_bus,
                host=host,
                mode="Unrated",
                slots=1,
                party_code=None,
                expires_in=timedelta(minutes=30),
            )
        lobby_id = lobby.id

    async def attempt(user_id: int) -> str:
        async with session_factory() as session:
            async with session.begin():
                user = await upsert_user(session, user_id, f"P{user_id}")
                try:
                    await join_lobby(session, event_bus, lobby_id=lobby_id, user=user)
                    return "ok"
                except LobbyFullError:
                    return "full"

    results = await asyncio.gather(attempt(51), attempt(52))
    assert sorted(results) == ["full", "ok"]


@pytest.mark.asyncio
async def test_join_rejects_above_max_rank(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 60, "Host60", rank="Gold")
    await upsert_user(session, 61, "P61", rank="Diamond")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 60, "Host60", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            min_rank="Silver",
            max_rank="Gold",
            ranks_verified=True,
            expires_in=timedelta(minutes=30),
        )

    async with session.begin():
        player = await upsert_user(session, 61, "P61", rank="Diamond")
        with pytest.raises(LobbyNotJoinableError):
            await join_lobby(session, event_bus, lobby_id=lobby.id, user=player)


@pytest.mark.asyncio
async def test_close_lobby_as_host(session: AsyncSession, event_bus: EventBus) -> None:
    await _host(session, 70)
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 70, "Host70")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(minutes=30),
        )

    async with session.begin():
        closed = await close_lobby_as_host(session, event_bus, lobby_id=lobby.id, host_id=70)
    assert closed.state == LobbyState.closed


@pytest.mark.asyncio
async def test_host_no_active_lobby_after_expires_at(
    session: AsyncSession, event_bus: EventBus
) -> None:
    await _host(session, 80)
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 80, "Host80")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            expires_in=timedelta(minutes=-5),
        )

    assert lobby.state == LobbyState.open
    async with session.begin():
        active = await get_host_active_lobby(session, 80)
    assert active is None
    async with session.begin():
        closable = await get_host_active_lobby(session, 80, include_past_ttl=True)
    assert closable is not None
    assert closable.id == lobby.id


@pytest.mark.asyncio
async def test_concurrent_close_and_expire(
    session_factory: async_sessionmaker[AsyncSession], event_bus: EventBus
) -> None:
    now = datetime.now(UTC)
    async with session_factory() as session:
        async with session.begin():
            host = await upsert_user(session, 83, "Host83")
            lobby = await create_lobby(
                session,
                event_bus,
                host=host,
                mode="Unrated",
                slots=2,
                party_code=None,
                expires_in=timedelta(seconds=0),
            )
            lobby.expires_at = now
        lobby_id = lobby.id

    async def do_close() -> None:
        async with session_factory() as session:
            async with session.begin():
                await close_lobby(session, event_bus, lobby_id=lobby_id, now=now)

    async def do_expire() -> None:
        async with session_factory() as session:
            async with session.begin():
                await expire_due_lobbies(session, event_bus, now=now)

    await asyncio.gather(do_close(), do_expire())

    async with session_factory() as session:
        final = await get_lobby_detail(session, lobby_id)
    assert final.state in (LobbyState.closed, LobbyState.expired)
