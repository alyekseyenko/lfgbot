from unittest.mock import MagicMock

from app.bot.discord_roles import extract_valorant_rank_from_member, find_rank_role


def test_find_rank_role_uses_mapping_first() -> None:
    guild = MagicMock()
    mapped_role = MagicMock()
    mapped_role.name = "Gold Rank"
    guild.get_role.return_value = mapped_role
    guild.roles = []

    role = find_rank_role(
        guild,
        "Gold",
        role_mappings={("valorant_rank", "Gold"): 12345},
    )
    assert role is mapped_role
    guild.get_role.assert_called_once_with(12345)


def test_extract_valorant_rank_from_member_uses_admin_mapping() -> None:
    platinum_role = type("Role", (), {"id": 99, "name": "PLATINUM"})()
    member = type("Member", (), {"roles": [platinum_role]})()
    rank = extract_valorant_rank_from_member(
        member,
        role_mappings={("valorant_rank", "Platinum"): 99},
    )
    assert rank == "Platinum"
