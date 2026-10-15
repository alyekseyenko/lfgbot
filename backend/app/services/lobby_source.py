from __future__ import annotations

LOBBY_SOURCE_SLASH = "slash"
LOBBY_SOURCE_PANEL = "panel"
LOBBY_SOURCE_CHAT = "chat"
LOBBY_SOURCE_UNKNOWN = "unknown"

LOBBY_CREATE_SOURCES: frozenset[str] = frozenset(
    {LOBBY_SOURCE_SLASH, LOBBY_SOURCE_PANEL, LOBBY_SOURCE_CHAT, LOBBY_SOURCE_UNKNOWN}
)


def normalize_lobby_source(raw: str | None) -> str:
    if raw and raw in LOBBY_CREATE_SOURCES:
        return raw
    return LOBBY_SOURCE_UNKNOWN
