from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.bot.embeds import build_lobby_embed
from app.db.models import Lobby, LobbyState, User
from app.services.lfg_embed_style import LobbyEmbedStyle


def _lobby(host_rank: str = "Diamond") -> Lobby:
    host = User(discord_id=1, name="Host", rank=host_rank)
    return Lobby(
        id=uuid4(),
        host_id=1,
        mode="Competitivo",
        slots=3,
        party_code=None,
        party_code_public=True,
        min_rank="Gold",
        max_rank="Immortal",
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )


def test_build_lobby_embed_rank_colour() -> None:
    lobby = _lobby()
    style = LobbyEmbedStyle(color_source="min_rank")
    built = build_lobby_embed(lobby, embed_style=style)
    assert built.embed.colour.value == int("ECA82E", 16)


def test_build_lobby_embed_immune_title() -> None:
    lobby = _lobby()
    style = LobbyEmbedStyle(
        immune_embed_enabled=True,
        immune_embed_label="VIP Comunidade",
        immune_role_ids=(99,),
    )
    built = build_lobby_embed(lobby, embed_style=style)
    assert "VIP Comunidade" not in built.embed.title
