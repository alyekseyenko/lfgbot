from __future__ import annotations

import re

_TAG_RE = re.compile(r"^[A-Za-z0-9]{3,5}$")
_NAME_MAX = 16


class RiotIdError(ValueError):
    pass


def format_riot_id(game_name: str | None, tag: str | None) -> str | None:
    if not game_name or not tag:
        return None
    return f"{game_name}#{tag}"


def validate_riot_id_parts(game_name: str, tag: str) -> tuple[str, str]:
    name = game_name.strip()
    tag_clean = tag.strip().lstrip("#")
    if not name or len(name) > _NAME_MAX:
        raise RiotIdError(f"O nome Riot tem de ter 1–{_NAME_MAX} caracteres.")
    if "#" in name:
        raise RiotIdError("O nome não pode incluir # — usa o campo da tag.")
    if not _TAG_RE.match(tag_clean):
        raise RiotIdError("A tag tem de ter 3–5 letras ou números.")
    return name, tag_clean.upper()


def parse_riot_id_field(value: str) -> tuple[str, str]:
    raw = value.strip()
    if "#" not in raw:
        raise RiotIdError("Formato: Nome#TAG")
    name_part, tag_part = raw.split("#", 1)
    return validate_riot_id_parts(name_part, tag_part)
