from __future__ import annotations

import pytest

from app.services.errors import PartyCodeInvalidError
from app.services.party_code import (
    clamp_party_code_max_length,
    normalize_party_code,
)


def test_clamp_party_code_max_length() -> None:
    assert clamp_party_code_max_length(6) == 6
    assert clamp_party_code_max_length(3) == 4
    assert clamp_party_code_max_length(99) == 12


def test_normalize_party_code_custom_length() -> None:
    assert normalize_party_code("abcd12", max_length=6) == "ABCD12"
    with pytest.raises(PartyCodeInvalidError):
        normalize_party_code("abcd12", max_length=8)
    assert normalize_party_code("abcd1234", max_length=8) == "ABCD1234"
