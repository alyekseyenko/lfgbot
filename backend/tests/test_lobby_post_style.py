from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.bot.embeds import build_lobby_embed
from app.core.events import EventBus
from app.db.models import Lobby, LobbyState, User
from app.services.errors import LobbyNotJoinableError
from app.services.lobby_post_style import (
    POST_STYLE_INTERACTIVE,
    POST_STYLE_SIMPLE,
    is_simple_post_style,
    normalize_post_style,
)
from app.services.lobbies import create_lobby, join_lobby


def test_normalize_post_style_defaults_simple() -> None:
    assert normalize_post_style(None) == POST_STYLE_SIMPLE
    assert normalize_post_style("unknown") == POST_STYLE_SIMPLE
    assert normalize_post_style(POST_STYLE_INTERACTIVE) == POST_STYLE_INTERACTIVE
    assert is_simple_post_style(POST_STYLE_SIMPLE)


def test_simple_embed_omits_players_field() -> None:
    host = User(discord_id=1, name="Host", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=1,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        party_code_public=True,
        min_rank="Gold",
        max_rank=None,
        post_style=POST_STYLE_SIMPLE,
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby)
    names = [f.name for f in built.embed.fields]
    assert "Jogadores" not in " ".join(names)
    assert any("party" in (n or "").lower() or "Código" in (n or "") for n in names)


@pytest.mark.asyncio
async def test_join_blocked_on_simple_lobby(session, event_bus: EventBus) -> None:
    host = User(discord_id=10, name="Host", rank="Gold")
    guest = User(discord_id=11, name="Guest", rank="Gold")
    session.add_all([host, guest])
    await session.flush()
    lobby = await create_lobby(
        session,
        event_bus,
        host=host,
        mode="Competitivo",
        slots=2,
        party_code="CODE1",
        expires_in=timedelta(minutes=30),
        post_style=POST_STYLE_SIMPLE,
    )
    await session.commit()
    with pytest.raises(LobbyNotJoinableError, match="simples"):
        await join_lobby(session, event_bus, lobby_id=lobby.id, user=guest)
