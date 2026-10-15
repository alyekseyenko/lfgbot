from __future__ import annotations

import re

VALORANT_RANKS: tuple[str, ...] = (
    "Unranked",
    "Iron",
    "Bronze",
    "Silver",
    "Gold",
    "Platinum",
    "Diamond",
    "Ascendant",
    "Immortal",
    "Radiant",
)

AGENT_ROLES: frozenset[str] = frozenset(
    {"Initiator", "Duelist", "Controller", "Sentinel"},
)

_RANK_ALIASES: dict[str, str] = {
    "unranked": "Unranked",
    "iron": "Iron",
    "bronze": "Bronze",
    "silver": "Silver",
    "gold": "Gold",
    "platinum": "Platinum",
    "plat": "Platinum",
    "diamond": "Diamond",
    "dia": "Diamond",
    "ascendant": "Ascendant",
    "asc": "Ascendant",
    "immortal": "Immortal",
    "imm": "Immortal",
    "radiant": "Radiant",
    "rad": "Radiant",
}

_RANK_RANGE_PATTERN = re.compile(r"@?([A-Za-z]+)\s*[-–/]\s*@?([A-Za-z]+)")
_MIN_RANK_PATTERN = re.compile(r"(?i)(?:min|mín|mínimo)\s*@?([A-Za-z]+)")
_MAX_RANK_PATTERN = re.compile(r"(?i)(?:max|máx|máximo|ate|até)\s*@?([A-Za-z]+)")


def normalize_rank_name(raw: str) -> str | None:
    key = raw.strip().lstrip("@").replace("_", " ").lower()
    if not key:
        return None
    if key in _RANK_ALIASES:
        return _RANK_ALIASES[key]
    for rank in VALORANT_RANKS:
        if rank.lower() == key:
            return rank
    return None


def rank_tier(rank: str | None) -> int:
    if rank is None:
        return -1
    normalized = normalize_rank_name(rank)
    if normalized is None:
        return -1
    try:
        return VALORANT_RANKS.index(normalized)
    except ValueError:
        return -1


def validate_rank_range(min_rank: str | None, max_rank: str | None) -> None:
    from app.services.errors import RankRangeError

    if min_rank and normalize_rank_name(min_rank) is None:
        raise RankRangeError(f"Rank mínimo inválido: {min_rank}")
    if max_rank and normalize_rank_name(max_rank) is None:
        raise RankRangeError(f"Rank máximo inválido: {max_rank}")
    min_tier = rank_tier(min_rank)
    max_tier = rank_tier(max_rank)
    if min_rank and min_tier < 0:
        raise RankRangeError(f"Rank mínimo inválido: {min_rank}")
    if max_rank and max_tier < 0:
        raise RankRangeError(f"Rank máximo inválido: {max_rank}")
    if min_rank and max_rank and min_tier > max_tier:
        raise RankRangeError(
            f"O rank mínimo ({min_rank}) não pode ser superior ao máximo ({max_rank})."
        )


def rank_meets_minimum(user_rank: str | None, min_rank: str | None) -> bool:
    if not min_rank:
        return True
    required = rank_tier(min_rank)
    if required < 0:
        return True
    user_tier = rank_tier(user_rank)
    if user_tier < 0:
        return False
    return user_tier >= required


def rank_meets_maximum(user_rank: str | None, max_rank: str | None) -> bool:
    if not max_rank:
        return True
    cap = rank_tier(max_rank)
    if cap < 0:
        return True
    user_tier = rank_tier(user_rank)
    if user_tier < 0:
        return True
    return user_tier <= cap


def rank_fits_lobby(
    user_rank: str | None,
    min_rank: str | None,
    max_rank: str | None,
) -> bool:
    return rank_meets_minimum(user_rank, min_rank) and rank_meets_maximum(
        user_rank, max_rank
    )


def format_rank(rank: str | None) -> str:
    if not rank:
        return "Sem rank"
    return rank


def extract_rank_bounds_from_text(text: str) -> tuple[str | None, str | None]:
    lowered = text.lower()
    if "qlqr" in lowered or "qualquer rank" in lowered or "any rank" in lowered:
        return None, None

    range_match = _RANK_RANGE_PATTERN.search(text)
    if range_match:
        first = normalize_rank_name(range_match.group(1))
        second = normalize_rank_name(range_match.group(2))
        if first and second:
            if rank_tier(first) <= rank_tier(second):
                return first, second
            return second, first

    min_rank: str | None = None
    max_rank: str | None = None

    min_match = _MIN_RANK_PATTERN.search(text)
    if min_match:
        min_rank = normalize_rank_name(min_match.group(1))

    max_match = _MAX_RANK_PATTERN.search(text)
    if max_match:
        max_rank = normalize_rank_name(max_match.group(1))

    if min_rank is None and max_rank is None:
        for token in re.findall(r"@?([A-Za-z]+)", text):
            normalized = normalize_rank_name(token)
            if normalized:
                return normalized, None

    return min_rank, max_rank


def extract_min_rank_from_text(text: str) -> str | None:
    min_rank, _max_rank = extract_rank_bounds_from_text(text)
    return min_rank


def extract_max_rank_from_text(text: str) -> str | None:
    _min_rank, max_rank = extract_rank_bounds_from_text(text)
    return max_rank
