from datetime import date

from app.bot.ranking_embed import build_weekly_ranking_embed
from app.services.gamification import WeeklyEntry


def test_ranking_embed_has_medals_and_fields() -> None:
    week = date(2026, 10, 13)
    hosts = [WeeklyEntry(user_id=1, count=3)]
    players = [
        WeeklyEntry(user_id=2, count=2),
        WeeklyEntry(user_id=3, count=1),
    ]
    names = {1: "HostA", 2: "P1", 3: "P2"}
    embed = build_weekly_ranking_embed(week, hosts, players, names)
    assert embed.title == "Ranking LFG"
    host_field = next(f for f in embed.fields if f.name == "Top hosts")
    assert "🥇" in host_field.value
    assert "HostA" in host_field.value
    player_field = next(f for f in embed.fields if f.name == "Top jogadores")
    assert "🥇" in player_field.value and "🥈" in player_field.value
