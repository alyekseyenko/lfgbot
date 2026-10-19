from collections import Counter

import discord

from app.bot.lfg_panel import (
    PANEL_EMBED_DESCRIPTION,
    PANEL_EMBED_TITLE,
    RANK_SELECT_NONE,
    RANKS_MODE_VERIFIED,
    CreateGroupPanelView,
    SimpleRankPublishView,
    build_panel_embed,
    is_panel_message,
    parse_optional_panel_rank,
    parse_panel_slots,
    rank_extras_prompt,
    rank_from_select_value,
    rank_select_options,
    rank_select_options_with_default,
    ranks_mode_select_options,
)
from app.services.lfg_embed_style import LfgEmbedPanelSettings, LobbyEmbedStyle


def _select_count_per_row(view: discord.ui.View) -> dict[int, int]:
    counts: Counter[int] = Counter()
    for item in view.children:
        if isinstance(item, discord.ui.Select):
            counts[item.row or 0] += 1
    return dict(counts)


def test_panel_embed_describes_current_flow() -> None:
    embed = build_panel_embed()
    assert PANEL_EMBED_TITLE in (embed.title or "")
    assert "🎯" in (embed.title or "")
    assert PANEL_EMBED_DESCRIPTION in (embed.description or "")
    assert "Criar grupo" in PANEL_EMBED_DESCRIPTION
    assert "Publicar" in PANEL_EMBED_DESCRIPTION
    assert "/procurar" not in PANEL_EMBED_DESCRIPTION
    assert "/fechar" not in PANEL_EMBED_DESCRIPTION
    assert "escolhe o tipo" not in PANEL_EMBED_DESCRIPTION.lower()


def test_panel_embed_minimal_visibility() -> None:
    style = LobbyEmbedStyle(
        panel_thumbnail_url="https://example.com/t.png",
        panel_footer_brand="Marca",
        panel_visibility=LfgEmbedPanelSettings(
            show_title=True,
            show_lead=False,
            show_body=False,
            show_cta=False,
            show_guide=False,
            show_footer=False,
            show_thumbnail=False,
            show_banner=False,
        ),
    )
    embed = build_panel_embed(style, guide_channel_id=123)
    assert PANEL_EMBED_TITLE in (embed.title or "")
    assert not (embed.description or "").strip()
    assert embed.footer is None or not (embed.footer.text or "").strip()
    assert embed.thumbnail is None or not getattr(embed.thumbnail, "url", None)


def test_panel_embed_custom_brand_colour() -> None:
    style = LobbyEmbedStyle(
        panel_color="112233",
        panel_footer_brand="PT Valorant",
        footer_brand="Outro",
    )
    embed = build_panel_embed(style)
    assert embed.colour.value == 0x112233
    assert embed.footer is not None
    assert embed.footer.text == "PT Valorant"


def test_parse_panel_slots_valid() -> None:
    assert parse_panel_slots("2") == 2
    assert parse_panel_slots(" 4 ") == 4


def test_parse_panel_slots_invalid() -> None:
    assert parse_panel_slots("0") is None
    assert parse_panel_slots("5") is None
    assert parse_panel_slots("") is None
    assert parse_panel_slots("x") is None


def test_is_panel_message() -> None:
    class Author:
        id = 1

    class Embed:
        title = PANEL_EMBED_TITLE

    class Msg:
        author = Author()
        embeds = [Embed()]

    assert is_panel_message(Msg(), 1) is True
    assert is_panel_message(Msg(), 2) is False


def test_rank_from_select_value() -> None:
    assert rank_from_select_value(RANK_SELECT_NONE) is None
    assert rank_from_select_value("Gold") == "Gold"


def test_parse_optional_panel_rank() -> None:
    assert parse_optional_panel_rank("") is None
    assert parse_optional_panel_rank("  gold ") == "Gold"
    assert parse_optional_panel_rank("plat") == "Platinum"
    assert parse_optional_panel_rank("nope") is None


def test_rank_select_options_with_default_marks_selection() -> None:
    opts = rank_select_options_with_default("Gold")
    defaults = [o for o in opts if o.default]
    assert len(defaults) == 1
    assert defaults[0].value == "Gold"
    none_opts = rank_select_options_with_default(None)
    none_default = [o for o in none_opts if o.default]
    assert len(none_default) == 1
    assert none_default[0].value == RANK_SELECT_NONE


def test_rank_select_options_include_none_and_ranks() -> None:
    values = [opt.value for opt in rank_select_options()]
    assert values[0] == RANK_SELECT_NONE
    assert "Gold" in values
    assert "Radiant" in values
    assert "Unranked" in values


def test_rank_extras_prompt_highlights_slots_and_code() -> None:
    text = rank_extras_prompt(slots=2, party_code="ABC123")
    assert "**2**" in text
    assert "`ABC123`" in text
    assert "/procurar" in text
    empty = rank_extras_prompt(slots=1, party_code=None)
    assert "sem código" in empty


def test_ranks_mode_select_includes_verified() -> None:
    values = [opt.value for opt in ranks_mode_select_options()]
    assert RANKS_MODE_VERIFIED in values


def test_simple_rank_publish_view_at_most_one_select_per_row() -> None:
    panel = CreateGroupPanelView()
    view = SimpleRankPublishView(panel, slots=2, party_code="ABC123", user_id=1)
    per_row = _select_count_per_row(view)
    assert all(count <= 1 for count in per_row.values())
