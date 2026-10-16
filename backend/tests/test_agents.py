from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventBus
from app.services.agents import parse_wanted_agents_csv, serialize_wanted_agents
from app.services.errors import LobbyNotJoinableError
from app.services.lobbies import create_lobby, join_lobby
from app.services.users import upsert_user


def test_serialize_wanted_agents() -> None:
    assert serialize_wanted_agents(["Initiator", "Sentinel"]) == "Initiator,Sentinel"
    assert parse_wanted_agents_csv("Initiator,Sentinel") == ["Initiator", "Sentinel"]


@pytest.mark.asyncio
async def test_join_requires_wanted_agent(session: AsyncSession, event_bus: EventBus) -> None:
    await upsert_user(session, 901, "Host", rank="Gold")
    await upsert_user(session, 902, "Duelist", rank="Gold")
    await session.commit()

    async with session.begin():
        host = await upsert_user(session, 901, "Host", rank="Gold")
        lobby = await create_lobby(
            session,
            event_bus,
            host=host,
            mode="Unrated",
            slots=2,
            party_code=None,
            wanted_agents=["Initiator"],
            expires_in=timedelta(minutes=30),
        )

    async with session.begin():
        guest = await upsert_user(session, 902, "Duelist", rank="Gold")
        with pytest.raises(LobbyNotJoinableError):
            await join_lobby(
                session,
                event_bus,
                lobby_id=lobby.id,
                user=guest,
                applicant_agents=frozenset({"Duelist"}),
            )

    async with session.begin():
        guest = await upsert_user(session, 902, "Duelist", rank="Gold")
        member = await join_lobby(
            session,
            event_bus,
            lobby_id=lobby.id,
            user=guest,
            applicant_agents=frozenset({"Initiator"}),
        )
    assert member.user_id == 902
