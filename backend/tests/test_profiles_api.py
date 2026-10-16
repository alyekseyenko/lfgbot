from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import create_api_app
from app.core.config import Settings
from app.core.events import EventBus
from app.services.guild_config import GuildConfigService
from app.services.player_profile import build_player_profile
from app.services.riot_id import parse_riot_id_field
from app.services.users import upsert_user


@pytest.fixture
def api_client(session_factory: async_sessionmaker[AsyncSession]) -> TestClient:
    settings = Settings(session_secret="test-secret", discord_guild_id=42)
    app = create_api_app(settings, session_factory, None, GuildConfigService(settings), EventBus())
    return TestClient(app)


@pytest.mark.asyncio
async def test_build_player_profile_riot_id_visibility(session: AsyncSession) -> None:
    user = await upsert_user(session, 1001, "Player", rank="Gold")
    user.riot_game_name = "Zecas"
    user.riot_tag = "EUW"
    await session.flush()

    public = await build_player_profile(
        session,
        None,
        target_id=1001,
        viewer_id=None,
        guild_ids=[],
        include_riot_id=False,
    )
    authed = await build_player_profile(
        session,
        None,
        target_id=1001,
        viewer_id=2000,
        guild_ids=[],
        include_riot_id=True,
    )
    assert public is not None
    assert public.riot_id is None
    assert authed is not None
    assert authed.riot_id == "Zecas#EUW"


@pytest.mark.asyncio
async def test_user_riot_id_persisted(session: AsyncSession) -> None:
    user = await upsert_user(session, 1002, "Owner")
    name, tag = parse_riot_id_field("Zecas#EUW")
    user.riot_game_name = name
    user.riot_tag = tag
    await session.flush()

    view = await build_player_profile(
        session,
        None,
        target_id=1002,
        viewer_id=1002,
        guild_ids=[],
        include_riot_id=True,
    )
    assert view is not None
    assert view.riot_id == "Zecas#EUW"
    assert view.is_self is True


@pytest.mark.asyncio
async def test_profile_agents_list_empty(session: AsyncSession) -> None:
    await upsert_user(session, 1003, "Solo")
    await session.flush()
    view = await build_player_profile(
        session,
        None,
        target_id=1003,
        viewer_id=None,
        guild_ids=[],
        include_riot_id=False,
    )
    assert view is not None
    assert view.agents == []


def test_patch_profile_requires_session(api_client: TestClient) -> None:
    assert api_client.patch("/profiles/me", json={"riot_id": "A#BCD"}).status_code == 401
