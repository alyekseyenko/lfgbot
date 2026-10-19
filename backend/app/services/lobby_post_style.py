from __future__ import annotations

POST_STYLE_SIMPLE = "simple"
POST_STYLE_INTERACTIVE = "interactive"
POST_STYLES = frozenset({POST_STYLE_SIMPLE, POST_STYLE_INTERACTIVE})


def normalize_post_style(raw: str | None) -> str:
    if raw == POST_STYLE_INTERACTIVE:
        return POST_STYLE_INTERACTIVE
    return POST_STYLE_SIMPLE


def is_simple_post_style(style: str | None) -> bool:
    return normalize_post_style(style) == POST_STYLE_SIMPLE


def resolve_post_style_for_guild(
    requested: str | None,
    *,
    simple_enabled: bool = True,
    detailed_enabled: bool = True,
) -> str:
    """Aplica flags do admin: só modos permitidos."""
    style = normalize_post_style(requested)
    if simple_enabled and detailed_enabled:
        return style
    if not simple_enabled and not detailed_enabled:
        return POST_STYLE_SIMPLE
    if style == POST_STYLE_SIMPLE and not simple_enabled:
        return POST_STYLE_INTERACTIVE
    if style == POST_STYLE_INTERACTIVE and not detailed_enabled:
        return POST_STYLE_SIMPLE
    return style
