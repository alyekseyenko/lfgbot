from app.services.guild_config import GuildRuntimeConfig
from app.services.lfg_embed_style import (
    lfg_embed_simple_to_storage,
    normalize_lfg_embed_detailed,
    normalize_lfg_embed_panel,
    normalize_lfg_embed_simple,
    normalize_lfg_embed_simple_custom_texts,
    simple_lobby_embed_style_from_config,
)


def test_normalize_simple_custom_texts_filters_keys() -> None:
    out = normalize_lfg_embed_simple_custom_texts(
        {
            "field_party_code": "Código",
            "lobby_cta_open": "ignored",
            "lobby_simple_hint": "Olá",
        }
    )
    assert out == {"field_party_code": "Código", "lobby_simple_hint": "Olá"}


def test_simple_embed_style_defaults_minimal() -> None:
    simple = normalize_lfg_embed_simple({}, fallback_footer_brand="LFG Valorant")
    assert simple.decorative is False
    assert simple.show_author is False
    assert simple.color_source == "min_rank"
    assert simple.show_close_button is True


def test_normalize_simple_hides_close_button() -> None:
    simple = normalize_lfg_embed_simple(
        {"show_close_button": False},
        fallback_footer_brand="LFG Valorant",
    )
    assert simple.show_close_button is False
    stored = lfg_embed_simple_to_storage(simple)
    assert stored["show_close_button"] is False


def test_normalize_simple_hides_edit_button() -> None:
    simple = normalize_lfg_embed_simple(
        {"show_edit_button": False},
        fallback_footer_brand="LFG Valorant",
    )
    assert simple.show_edit_button is False
    stored = lfg_embed_simple_to_storage(simple)
    assert stored["show_edit_button"] is False


def test_simple_lobby_embed_style_from_config() -> None:
    simple = normalize_lfg_embed_simple(
        {"decorative": True, "competitive_color": "112233"},
        fallback_footer_brand="Brand",
    )
    cfg = GuildRuntimeConfig(
        discord_guild_id=1,
        lfg_channel_ids=(),
        announce_channel_id=None,
        weekly_leaderboard_anchor=None,
        reputation_channel_id=0,
        reputation_delay_minutes=50,
        reputation_enabled_at=None,
        reputation_negative_threshold=-15,
        reputation_negative_role_id=0,
        reputation_positive_threshold=25,
        reputation_positive_role_id=0,
        auto_format_messages=True,
        default_lfg_mode="Competitivo",
        gamification_enabled=False,
        stats_channel_id=0,
        log_channel_id=0,
        panel_sticky_enabled=True,
        lobby_ttl_minutes=45,
        party_code_max_length=6,
        immune_role_ids=(),
        lfg_embed_color_source="mode",
        rank_embed_colors={},
        lfg_embed_competitive_color="FF4655",
        lfg_embed_unrated_color="5E98D9",
        lfg_embed_full_color="C23B22",
        lfg_embed_inactive_color="4A4E5A",
        lfg_embed_decorative=True,
        lfg_embed_footer_brand="Brand",
        lfg_embed_banner_url=None,
        lfg_embed_custom_texts={},
        lfg_embed_show_author=True,
        lfg_embed_show_timestamp=True,
        lfg_embed_show_thumbnail=True,
        lfg_embed_banner_on_panel=True,
        lfg_embed_banner_on_lobby=True,
        lfg_panel_thumbnail_url=None,
        lfg_panel_color="FF4655",
        lfg_panel_footer_brand=None,
        lfg_panel_banner_url=None,
        lfg_panel_decorative=True,
        lfg_embed_thumbnail_url=None,
        lfg_embed_simple=simple,
        lfg_embed_detailed=normalize_lfg_embed_detailed({}),
        lfg_embed_panel=normalize_lfg_embed_panel({}),
        lfg_post_style_simple_enabled=True,
        lfg_post_style_detailed_enabled=True,
        immune_embed_enabled=True,
        immune_embed_color="FFD700",
        immune_embed_label="VIP",
        immune_embed_tiers=(),
        search_penalty_enabled=True,
        search_penalty_early_minutes=5,
        search_penalty_early_max_count=3,
        search_penalty_mid_minutes=15,
        search_penalty_severe_hours=12,
        host_recreate_cooldown_seconds=300,
        immune_host_recreate_cooldown_seconds=10,
        role_mappings={},
    )
    style = simple_lobby_embed_style_from_config(cfg)
    assert style.decorative is True
    assert style.competitive_color == "112233"
    assert style.banner_on_lobby is False
    assert style.immune_embed_enabled is True
