from types import SimpleNamespace

from app.bot.discord_roles import find_agent_role, find_rank_role, normalize_rank_name


def test_find_rank_role_by_name() -> None:
    guild = SimpleNamespace(
        roles=[
            SimpleNamespace(name="Silver", id=101),
            SimpleNamespace(name="Gold", id=102),
        ]
    )
    role = find_rank_role(guild, "Silver")
    assert role is not None
    assert role.id == 101


def test_find_agent_role() -> None:
    guild = SimpleNamespace(
        roles=[
            SimpleNamespace(name="Sentinel", id=201),
            SimpleNamespace(name="Initiator", id=202),
        ]
    )
    assert find_agent_role(guild, "Sentinel").id == 201
    assert find_agent_role(guild, "Duelist") is None


def test_normalize_strips_at() -> None:
    assert normalize_rank_name("@silver") == "Silver"
