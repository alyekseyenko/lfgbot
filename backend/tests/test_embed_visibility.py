from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.bot.embeds import build_lobby_embed
from app.db.models import Lobby, LobbyState, User
from app.services.lfg_embed_style import (
    LfgEmbedSimpleSettings,
    LobbyEmbedStyle,
    simple_settings_to_visibility,
)
from app.services.lobby_post_style import (
    POST_STYLE_INTERACTIVE,
    POST_STYLE_SIMPLE,
    resolve_post_style_for_guild,
)


def test_resolve_post_style_for_guild_clamps_modes() -> None:
    assert (
        resolve_post_style_for_guild(
            POST_STYLE_SIMPLE, simple_enabled=False, detailed_enabled=True
        )
        == POST_STYLE_INTERACTIVE
    )
    assert (
        resolve_post_style_for_guild(
            POST_STYLE_INTERACTIVE, simple_enabled=True, detailed_enabled=False
        )
        == POST_STYLE_SIMPLE
    )


def test_simple_embed_host_as_mention_in_author() -> None:
    simple = LfgEmbedSimpleSettings(
        show_title=False,
        show_hint=False,
        show_host_line=False,
        show_author=True,
        host_as_mention=True,
        show_party_code=False,
        show_slots=False,
        show_rank=False,
        show_expires=False,
        show_footer=False,
    )
    style = LobbyEmbedStyle(visibility=simple_settings_to_visibility(simple), show_author=True)
    host = User(discord_id=42, name="Jay", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=42,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        party_code_public=True,
        post_style="simple",
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby, embed_style=style)
    assert built.embed.author is not None
    assert "Jay" in (built.embed.author.name or "")
    assert "<@42>" not in (built.embed.author.name or "")
    assert built.content == "Criado por <@42>"
    assert "Criado por" not in (built.embed.description or "")
    assert 42 in built.mention_user_ids


def test_simple_embed_host_mention_on_same_line_as_party_code() -> None:
    simple = LfgEmbedSimpleSettings(
        show_title=False,
        show_hint=False,
        show_host_line=True,
        host_as_mention=True,
        show_party_code=True,
        show_slots=False,
        show_rank=False,
        show_expires=False,
        show_footer=False,
    )
    style = LobbyEmbedStyle(visibility=simple_settings_to_visibility(simple))
    host = User(discord_id=42, name="Jay", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=42,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        party_code_public=True,
        post_style="simple",
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby, embed_style=style)
    assert built.content == "Criado por <@42>"
    desc = built.embed.description or ""
    assert "Criado por" not in desc
    assert "ABC123" not in desc
    code_field = next(f for f in built.embed.fields if "ABC123" in (f.value or ""))
    assert "Código" in (code_field.name or "")
    assert "```" in (code_field.value or "")


def test_simple_embed_minimal_visibility() -> None:
    simple = LfgEmbedSimpleSettings(
        show_title=False,
        show_hint=False,
        show_expires=False,
        show_footer=False,
        host_as_mention=True,
        show_party_code=True,
        show_slots=True,
        show_rank=True,
        show_host_line=True,
    )
    style = LobbyEmbedStyle(visibility=simple_settings_to_visibility(simple))
    host = User(discord_id=42, name="Jay", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=42,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        party_code_public=True,
        post_style="simple",
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby, embed_style=style)
    assert built.embed.title is None
    assert built.embed.footer is None or not (built.embed.footer.text or "").strip()
    assert built.content == "Criado por <@42>"
    desc = built.embed.description or ""
    assert "Criado por" not in desc
    assert "ABC123" not in desc
    assert built.mention_user_ids == [42]
    assert any("ABC123" in (f.value or "") for f in built.embed.fields)
    names = [f.name for f in built.embed.fields]
    assert not any("Expira" in (n or "") for n in names)


def test_simple_lobby_view_omits_close_button() -> None:
    from app.bot.views import SimpleLobbyView, make_lobby_view

    hidden = SimpleLobbyView(
        uuid4(), show_close_button=False, show_edit_button=False
    )
    assert hidden.children == []
    shown = make_lobby_view(uuid4(), "simple", show_close_button=True)
    assert any(getattr(item, "label", None) == "Fechar" for item in shown.children)
    assert any(getattr(item, "label", None) == "Editar" for item in shown.children)
    detailed = make_lobby_view(uuid4(), "interactive", show_close_button=False)
    assert any(getattr(item, "label", None) == "Fechar" for item in detailed.children)


def test_simple_footer_mentions_slash_when_button_hidden() -> None:
    simple = LfgEmbedSimpleSettings(
        show_footer=True,
        show_close_button=False,
        show_edit_button=False,
        show_expires=True,
    )
    style = LobbyEmbedStyle(visibility=simple_settings_to_visibility(simple))
    host = User(discord_id=42, name="Jay", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=42,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        party_code_public=True,
        post_style="simple",
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby, embed_style=style)
    footer = (built.embed.footer.text or "") if built.embed.footer else ""
    assert "/fechar" in footer
    assert "/editar" in footer
    assert " · Editar · " not in footer


def test_simple_embed_custom_host_line_prefix() -> None:
    simple = LfgEmbedSimpleSettings(
        show_title=False,
        show_hint=False,
        show_host_line=True,
        host_as_mention=True,
        show_party_code=True,
        show_slots=False,
        show_rank=False,
        show_expires=False,
        show_footer=False,
    )
    style = LobbyEmbedStyle(
        visibility=simple_settings_to_visibility(simple),
        custom_texts={"host_line_prefix": "Pedido de"},
    )
    host = User(discord_id=42, name="Jay", rank="Gold")
    lobby = Lobby(
        id=uuid4(),
        host_id=42,
        mode="Competitivo",
        slots=2,
        party_code="ABC123",
        party_code_public=True,
        post_style="simple",
        state=LobbyState.open,
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
        host=host,
        members=[],
    )
    built = build_lobby_embed(lobby, embed_style=style)
    assert built.content == "Pedido de <@42>"
    assert "Criado por" not in (built.content or "")
    assert "Pedido de" not in (built.embed.description or "")
