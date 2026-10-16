from __future__ import annotations

import discord

from app.db.models import LobbyState
from app.services.lfg_embed_style import (
    ImmuneEmbedTier,
    LobbyEmbedStyle,
    immune_highlight_from_tiers,
    normalize_immune_embed_tiers,
    resolve_lobby_embed_colour,
    union_immune_role_ids_from_tiers,
)


def test_normalize_immune_embed_tiers_caps_at_five() -> None:
    raw = [{"label": f"T{i}", "color": "AABBCC", "role_ids": [i]} for i in range(10)]
    tiers = normalize_immune_embed_tiers(raw)
    assert len(tiers) == 5
    assert tiers[0].label == "T0"


def test_union_role_ids_preserves_order() -> None:
    tiers = (
        ImmuneEmbedTier(label="A", color="111111", role_ids=(1, 2)),
        ImmuneEmbedTier(label="B", color="222222", role_ids=(2, 3)),
    )
    assert union_immune_role_ids_from_tiers(tiers) == (1, 2, 3)


def test_tier_priority_one_beats_two() -> None:
    booster_role = type(
        "Role",
        (),
        {
            "id": 10,
            "position": 5,
            "name": "Booster",
            "colour": discord.Colour(0xFF73FA),
            "icon": None,
        },
    )()
    trust_role = type(
        "Role",
        (),
        {
            "id": 20,
            "position": 10,
            "name": "Confiança",
            "colour": discord.Colour(0x00FF00),
            "icon": None,
        },
    )()
    member = type("Member", (), {"roles": [trust_role, booster_role]})()
    tiers = (
        ImmuneEmbedTier(label="Booster VIP", color="FF73FA", role_ids=(10,)),
        ImmuneEmbedTier(label="Membro de confiança", color="00FF00", role_ids=(20,)),
    )
    highlight = immune_highlight_from_tiers(member, tiers)
    assert highlight is not None
    assert highlight.label == "Booster VIP"
    assert highlight.role_id == 10


def test_resolve_embed_uses_tier_label() -> None:
    host = type("Host", (), {"rank": "Gold", "discord_id": 1})()
    lobby = type(
        "Lobby",
        (),
        {
            "state": LobbyState.open,
            "mode": "Competitivo",
            "host": host,
            "min_rank": None,
            "max_rank": None,
        },
    )()
    role = type(
        "Role",
        (),
        {
            "id": 42,
            "position": 1,
            "name": "Doador",
            "colour": discord.Colour(0x112233),
            "icon": None,
        },
    )()
    member = type("Member", (), {"roles": [role]})()
    style = LobbyEmbedStyle(
        immune_embed_enabled=True,
        immune_embed_tiers=(ImmuneEmbedTier(label="Apoiante", color="112233", role_ids=(42,)),),
    )
    colour, immune = resolve_lobby_embed_colour(
        lobby,
        None,
        style,
        mode_colour=discord.Colour(0xFF4655),
        full_colour=discord.Colour(0xC23B22),
        inactive_colour=discord.Colour(0x4A4E5A),
        host_member=member,
    )
    assert immune is not None
    assert immune.label == "Apoiante"
    assert colour.value == 0x112233
