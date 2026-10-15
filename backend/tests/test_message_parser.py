from app.bot.message_parser import parse_lfg_message


def test_plus_and_code() -> None:
    parsed = parse_lfg_message("+3 OLI743 @PLATINUM")
    assert parsed is not None
    assert parsed.slots == 3
    assert parsed.party_code == "OLI743"
    assert parsed.min_rank == "Platinum"


def test_solo_with_code() -> None:
    parsed = parse_lfg_message("solo JQZ794")
    assert parsed is not None
    assert parsed.slots == 4
    assert parsed.party_code == "JQZ794"


def test_duo_only() -> None:
    parsed = parse_lfg_message("duo CSG726")
    assert parsed is not None
    assert parsed.slots == 3
    assert parsed.party_code == "CSG726"


def test_ignores_random_chat() -> None:
    assert parse_lfg_message("boa tarde malta") is None


def test_at_silver_alias() -> None:
    parsed = parse_lfg_message("+2 ABC123 @silver")
    assert parsed is not None
    assert parsed.min_rank == "Silver"
    assert parsed.max_rank is None


def test_silver_to_gold_range() -> None:
    parsed = parse_lfg_message("+2 ABC123 silver-gold")
    assert parsed is not None
    assert parsed.min_rank == "Silver"
    assert parsed.max_rank == "Gold"
