from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.bot.embeds import (
    DEFAULT_HOST_NO_RANK_FOOTER,
    allowed_mentions_for_lobby,
    build_lobby_embed,
)
from app.core.events import EventBus
from app.db.models import Lobby, LobbyState, User
from app.services.errors import LobbyNotJoinableError
from app.services.lfg_embed_style import ImmuneEmbedTier, LobbyEmbedStyle
from app.services.lobbies import create_lobby, join_lobby
from app.services.lobby_post_style import (
    POST_STYLE_INTERACTIVE,
    POST_STYLE_SIMPLE,
    is_simple_post_style,
    normalize_post_style,
)


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
    assert built.mention_user_ids == []
    assert "**Host**" in (built.embed.description or "")
    names = [f.name for f in built.embed.fields]
    assert "Jogadores" not in " ".join(names)
    assert any("Código" in (n or "") for n in names)
    rank_fields = [f for f in built.embed.fields if "Rank" in (f.name or "")]
    assert rank_fields
    assert "Gold" in rank_fields[0].value


def test_simple_embed_immune_title_and_thumbnail() -> None:
    booster = SimpleNamespace(
        id=10,
        position=5,
        name="Booster",
        colour=None,
        icon=SimpleNamespace(url="https://cdn.example/icon.png"),
        unicode_emoji=None,
    )
    host_member = SimpleNamespace(roles=[booster])
    host = User(discord_id=1, name="Host", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=1,
        mode="Competitivo",
        slots=2,
        party_code="ABC",
        party_code_public=True,
        post_style=POST_STYLE_SIMPLE,
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    style = LobbyEmbedStyle(
        immune_embed_enabled=True,
        immune_embed_tiers=(ImmuneEmbedTier(label="Apoiante VIP", color="FF73FA", role_ids=(10,)),),
    )
    built = build_lobby_embed(lobby, host_member=host_member, embed_style=style)
    assert built.embed.title == "Apoiante VIP"
    assert built.embed.thumbnail is not None
    assert built.embed.thumbnail.url == "https://cdn.example/icon.png"


def test_simple_embed_footer_host_rank_icon_without_immune() -> None:
    gold_role = SimpleNamespace(
        name="Gold",
        id=102,
        mention="<@&102>",
        unicode_emoji=None,
        icon=SimpleNamespace(url="https://cdn.example/gold.png"),
    )
    guild = SimpleNamespace(roles=[gold_role])
    host_member = SimpleNamespace(roles=[gold_role])
    host = User(discord_id=5, name="Host", rank="Silver")
    lobby = Lobby(
        id=uuid4(),
        host_id=5,
        mode="Competitivo",
        slots=2,
        party_code="X",
        party_code_public=True,
        post_style=POST_STYLE_SIMPLE,
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    mappings = {("valorant_rank", "Gold"): 102}
    built = build_lobby_embed(lobby, guild=guild, host_member=host_member, role_mappings=mappings)
    assert built.embed.footer is not None
    assert built.embed.footer.icon_url == "https://cdn.example/gold.png"
    assert DEFAULT_HOST_NO_RANK_FOOTER not in (built.embed.footer.text or "")


def test_simple_embed_footer_no_rank_on_discord() -> None:
    host_member = SimpleNamespace(roles=[])
    host = User(discord_id=6, name="Host", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=6,
        mode="Competitivo",
        slots=1,
        party_code="Y",
        party_code_public=True,
        post_style=POST_STYLE_SIMPLE,
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby, host_member=host_member)
    assert built.embed.footer is not None
    assert DEFAULT_HOST_NO_RANK_FOOTER in (built.embed.footer.text or "")
    assert built.embed.footer.icon_url is None


def test_simple_embed_rank_field_uses_role_mentions() -> None:
    diamond = SimpleNamespace(
        name="Diamond",
        id=501,
        mention="<@&501>",
        unicode_emoji=None,
        icon=None,
    )
    ascendant = SimpleNamespace(
        name="Ascendant",
        id=502,
        mention="<@&502>",
        unicode_emoji=None,
        icon=None,
    )
    guild = SimpleNamespace(roles=[diamond, ascendant])
    host = User(discord_id=99, name="Host", rank="Diamond")
    lobby = Lobby(
        id=uuid4(),
        host_id=99,
        mode="Competitivo",
        slots=1,
        party_code="QZK657",
        party_code_public=True,
        min_rank="Diamond",
        max_rank="Ascendant",
        post_style=POST_STYLE_SIMPLE,
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby, guild=guild)
    rank_fields = [f for f in built.embed.fields if "Rank" in (f.name or "")]
    assert rank_fields
    assert "<@&501>" in rank_fields[0].value
    assert "<@&502>" in rank_fields[0].value
    assert built.mention_role_ids == [501, 502]
    mentions = allowed_mentions_for_lobby(built)
    assert {r.id for r in mentions.roles} == {501, 502}


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
