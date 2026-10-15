import pytest

from app.services.errors import RankRangeError
from app.services.ranks import (
    extract_rank_bounds_from_text,
    rank_fits_lobby,
    rank_meets_maximum,
    validate_rank_range,
)


def test_rank_range_in_text() -> None:
    min_rank, max_rank = extract_rank_bounds_from_text("+2 ABC123 silver-gold")
    assert min_rank == "Silver"
    assert max_rank == "Gold"


def test_max_keyword() -> None:
    min_rank, max_rank = extract_rank_bounds_from_text("+1 XYZ123 max plat")
    assert min_rank is None
    assert max_rank == "Platinum"


def test_validate_range_order() -> None:
    with pytest.raises(RankRangeError):
        validate_rank_range("Diamond", "Gold")


def test_rank_fits_band() -> None:
    assert rank_fits_lobby("Gold", "Silver", "Platinum")
    assert not rank_fits_lobby("Diamond", "Silver", "Gold")
    assert rank_meets_maximum("Immortal", "Gold") is False
