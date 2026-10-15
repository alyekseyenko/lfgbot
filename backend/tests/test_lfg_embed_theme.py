from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.bot.embeds import build_lobby_embed
from app.db.models import Lobby, LobbyState, User
from app.services.lfg_embed_style import LobbyEmbedStyle


def _lobby() -> Lobby:
    host = User(discord_id=1, name="Host", rank="Gold")
    return Lobby(
        id=uuid4(),
        host_id=1,
        mode="Competitivo",
        slots=3,
        party_code="ABC123",
        party_code_public=True,
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )


def test_decorative_title_and_footer_brand() -> None:
    style = LobbyEmbedStyle(
        decorative=True,
        footer_brand="Comunidade PT",
        competitive_color="FF0000",
    )
    built = build_lobby_embed(_lobby(), embed_style=style)
    assert "⚔️" in built.embed.title
    assert "Comunidade PT" in (built.embed.footer.text or "")


def test_custom_mode_colour() -> None:
    style = LobbyEmbedStyle(competitive_color="00FF00", color_source="mode")
    built = build_lobby_embed(_lobby(), embed_style=style)
    assert built.embed.colour.value == int("00FF00", 16)
