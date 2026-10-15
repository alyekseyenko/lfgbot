from unittest.mock import MagicMock

from app.bot.discord_roles import find_rank_role


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
