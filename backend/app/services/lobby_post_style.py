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
