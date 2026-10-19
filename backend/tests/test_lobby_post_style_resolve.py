from app.services.lobby_post_style import (
    POST_STYLE_INTERACTIVE,
    POST_STYLE_SIMPLE,
    resolve_post_style_for_guild,
)


def test_both_modes_enabled_keeps_request() -> None:
    assert resolve_post_style_for_guild(POST_STYLE_SIMPLE) == POST_STYLE_SIMPLE
    assert resolve_post_style_for_guild(POST_STYLE_INTERACTIVE) == POST_STYLE_INTERACTIVE
