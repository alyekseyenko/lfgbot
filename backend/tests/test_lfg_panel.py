from app.services.lfg_embed_style import LobbyEmbedStyle

from app.bot.lfg_panel import (
    PANEL_EMBED_DESCRIPTION,
    PANEL_EMBED_TITLE,
    RANK_SELECT_NONE,
    RANKS_MODE_VERIFIED,
    build_panel_embed,
    is_panel_message,
    parse_optional_panel_rank,
    parse_panel_slots,
    rank_extras_prompt,
    rank_from_select_value,
    rank_select_options,
    ranks_mode_select_options,
)


def test_panel_embed_describes_current_flow() -> None:
    embed = build_panel_embed()
    assert PANEL_EMBED_TITLE in (embed.title or "")
    assert "🎯" in (embed.title or "")
    assert PANEL_EMBED_DESCRIPTION in (embed.description or "")
    assert "Criar grupo" in PANEL_EMBED_DESCRIPTION
    assert "/procurar" in PANEL_EMBED_DESCRIPTION


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
