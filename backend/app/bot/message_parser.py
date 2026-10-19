from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.party_code import (
    DEFAULT_PARTY_CODE_MAX_LENGTH,
    clamp_party_code_max_length,
)
from app.services.ranks import extract_rank_bounds_from_text

PLUS_SLOTS_PATTERN = re.compile(r"\+\s*([1-4])\b", re.IGNORECASE)
SOLO_PATTERN = re.compile(r"\bsolo\b", re.IGNORECASE)
DUO_PATTERN = re.compile(r"\bduo\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ParsedLfgMessage:
    slots: int
    party_code: str | None
    min_rank: str | None
    max_rank: str | None


def _party_code_pattern(max_length: int) -> re.Pattern[str]:
    length = clamp_party_code_max_length(max_length)
    return re.compile(rf"\b([A-Z0-9]{{{length}}})\b")


def _pick_party_code(text: str, max_length: int) -> str | None:
    upper = text.upper()
    pattern = _party_code_pattern(max_length)
    candidates = [
        match.group(1)
        for match in pattern.finditer(upper)
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


def parse_lfg_message(
    content: str,
    *,
    party_code_max_length: int = DEFAULT_PARTY_CODE_MAX_LENGTH,
) -> ParsedLfgMessage | None:
    text = content.strip()
    if len(text) < 3:
        return None

    slots = _pick_slots(text)
    party_code = _pick_party_code(text, party_code_max_length)
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
