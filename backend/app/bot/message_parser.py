from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.ranks import extract_rank_bounds_from_text

# Códigos Valorant: 6 caracteres, pelo menos um dígito.
PARTY_CODE_PATTERN = re.compile(r"\b([A-Z0-9]{6})\b")
PLUS_SLOTS_PATTERN = re.compile(r"\+\s*([1-4])\b", re.IGNORECASE)
SOLO_PATTERN = re.compile(r"\bsolo\b", re.IGNORECASE)
DUO_PATTERN = re.compile(r"\bduo\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParsedLfgMessage:
    slots: int
    party_code: str | None
    min_rank: str | None
    max_rank: str | None


def _pick_party_code(text: str) -> str | None:
    upper = text.upper()
    candidates = [
        match.group(1)
        for match in PARTY_CODE_PATTERN.finditer(upper)
        if any(ch.isdigit() for ch in match.group(1))
    ]
    if not candidates:
        return None
    return candidates[-1]


def _pick_slots(text: str) -> int | None:
    plus = PLUS_SLOTS_PATTERN.search(text)
    if plus:
        return int(plus.group(1))
    if SOLO_PATTERN.search(text):
        return 4
    if DUO_PATTERN.search(text):
        return 3
    return None


def parse_lfg_message(content: str) -> ParsedLfgMessage | None:
    text = content.strip()
    if len(text) < 3:
        return None

    slots = _pick_slots(text)
    party_code = _pick_party_code(text)
    if slots is None and party_code is None:
        return None
    if slots is None:
        slots = 2

    min_rank, max_rank = extract_rank_bounds_from_text(text)

    return ParsedLfgMessage(
        slots=slots,
        party_code=party_code,
        min_rank=min_rank,
        max_rank=max_rank,
    )
