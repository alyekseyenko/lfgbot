from app.bot.embeds import _slots_meter, _status_label, _strike_main_text
from app.db.models import LobbyState


def test_slots_meter() -> None:
    assert "2" in _slots_meter(1, 3, False)
    assert "▰" in _slots_meter(2, 2, False)
    assert "🟥" in _slots_meter(1, 2, True)


def test_status_labels() -> None:
    assert _status_label(LobbyState.open, False) == "Aberto"
    assert _status_label(LobbyState.full, False) == "Cheio"
    assert _status_label(LobbyState.open, True) == "ABERTO"


def test_strike_main_text_when_inactive() -> None:
    assert _strike_main_text("Competitivo · Fechado", True) == "~~Competitivo · Fechado~~"
    assert _strike_main_text("Aberto", False) == "Aberto"
