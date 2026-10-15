from app.services.lfg_embed_style import (
    LFG_EMBED_TEXT_LIMITS,
    embed_custom_text,
    normalize_lfg_embed_custom_texts,
)
from app.services.lfg_embed_style import LobbyEmbedStyle


def test_normalize_custom_texts_truncates_and_filters() -> None:
    raw = {
        "panel_title": "x" * 300,
        "lobby_cta_open": "  Olá  ",
        "unknown_key": "nope",
    }
    out = normalize_lfg_embed_custom_texts(raw)
    assert len(out["panel_title"]) == LFG_EMBED_TEXT_LIMITS["panel_title"]
    assert out["lobby_cta_open"] == "Olá"
    assert "unknown_key" not in out


def test_embed_custom_text_fallback() -> None:
    style = LobbyEmbedStyle(custom_texts={"panel_title": "Custom"})
    assert embed_custom_text(style, "panel_title", "Default") == "Custom"
    assert embed_custom_text(style, "panel_cta", "Default") == "Default"
    assert embed_custom_text(None, "panel_cta", "Default") == "Default"
