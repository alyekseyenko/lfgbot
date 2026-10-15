from __future__ import annotations

import pytest

from app.services.riot_id import RiotIdError, format_riot_id, parse_riot_id_field, validate_riot_id_parts


def test_format_riot_id() -> None:
    assert format_riot_id("Zecas", "EUW") == "Zecas#EUW"
    assert format_riot_id(None, "EUW") is None


def test_validate_riot_id_parts() -> None:
    name, tag = validate_riot_id_parts("Zecas", "euw1")
    assert name == "Zecas"
    assert tag == "EUW1"


def test_parse_riot_id_field() -> None:
    name, tag = parse_riot_id_field("Zecas#EUW")
    assert (name, tag) == ("Zecas", "EUW")


def test_parse_riot_id_invalid() -> None:
    with pytest.raises(RiotIdError):
        parse_riot_id_field("NoTag")


def test_validate_name_with_hash() -> None:
    with pytest.raises(RiotIdError):
        validate_riot_id_parts("Bad#Name", "TAG")
