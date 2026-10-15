from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.services.lobbies import create_lobby, join_lobby
from app.services.users import upsert_user


@pytest.mark.asyncio
async def test_informative_ranks_do_not_block_join(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 1101, "Host", rank="Gold")
    await upsert_user(session, 1102, "Low", rank="Iron")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 1101, "Host", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            min_rank="Diamond",
            max_rank="Diamond",
            ranks_verified=False,
            expires_in=timedelta(minutes=30),
        )
        guest = await upsert_user(session, 1102, "Low", rank="Iron")
        member = await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest)
    assert member.user_id == 1102
