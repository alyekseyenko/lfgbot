from types import SimpleNamespace

import discord

from app.db.models import LobbyState
from app.services.lfg_embed_style import (
    LobbyEmbedStyle,
    member_has_immune_role,
    normalize_rank_embed_colors,
    parse_embed_hex_color,
    rank_embed_colour,
    resolve_lobby_embed_colour,
)


def test_parse_embed_hex_color() -> None:
    assert parse_embed_hex_color("#ffd700", default="000000") == "FFD700"
    assert parse_embed_hex_color("bad", default="AABBCC") == "AABBCC"


def test_normalize_rank_embed_colors() -> None:
    raw = {"gold": "#ECA82E", "invalid": "zzz", "Iron": "514F4A"}
    out = normalize_rank_embed_colors(raw)
    assert out["Gold"] == "ECA82E"
    assert out["Iron"] == "514F4A"
    assert "invalid" not in out


def test_rank_embed_colour_uses_defaults() -> None:
    colour = rank_embed_colour("Radiant", {})
    assert colour is not None
    assert colour.value == int("F4E19D", 16)


def test_member_has_immune_role() -> None:
    role = SimpleNamespace(id=99, position=1)
    member = SimpleNamespace(roles=[role])
    assert member_has_immune_role(member, (99,))
    assert not member_has_immune_role(member, (1,))


def test_resolve_colour_host_rank() -> None:
    host = SimpleNamespace(rank="Gold")
    lobby = SimpleNamespace(
        state=LobbyState.open,
        mode="Competitivo",
        host=host,
        min_rank=None,
        max_rank=None,
    )
    style = LobbyEmbedStyle(color_source="host_rank", rank_embed_colors={})
    colour, immune = resolve_lobby_embed_colour(
        lobby,
        None,
        style,
        mode_colour=discord.Colour(0xFF4655),
        full_colour=discord.Colour(0xC23B22),
        inactive_colour=discord.Colour(0x4A4E5A),
    )
    assert immune is None
    assert colour.value == int("ECA82E", 16)


def test_resolve_colour_immune_overrides_rank() -> None:
    host = SimpleNamespace(rank="Gold", discord_id=1)
    lobby = SimpleNamespace(
        state=LobbyState.open,
        mode="Competitivo",
        host=host,
        min_rank=None,
        max_rank=None,
    )
    role = SimpleNamespace(
        id=42,
        position=1,
        name="VIP",
        colour=discord.Colour(0x112233),
        icon=None,
    )
    member = SimpleNamespace(roles=[role])
    guild = SimpleNamespace(get_member=lambda _uid: member)
    style = LobbyEmbedStyle(
        color_source="host_rank",
        immune_role_ids=(42,),
        immune_embed_enabled=True,
        immune_embed_color="112233",
    )
    member = SimpleNamespace(roles=[role])
    colour, immune = resolve_lobby_embed_colour(
        lobby,
        guild,
        style,
        mode_colour=discord.Colour(0xFF4655),
        full_colour=discord.Colour(0xC23B22),
        inactive_colour=discord.Colour(0x4A4E5A),
        host_member=member,
    )
    assert immune is not None
    assert colour.value == 0x112233
