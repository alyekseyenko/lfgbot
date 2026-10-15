from __future__ import annotations

from types import SimpleNamespace

from app.services.settings_audit import (
    build_dashboard_settings_audit,
    filter_changed_settings_patch,
)


def _row(**kwargs: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "lfg_channel_ids": [1, 2],
        "log_channel_id": 0,
        "stats_channel_id": 0,
        "auto_format_messages": True,
        "gamification_enabled": False,
        "immune_embed_tiers": [],
        "immune_role_ids": [],
        "rank_embed_colors": {},
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_filter_ignores_unchanged_full_dashboard_payload() -> None:
    row = _row()
    patch = {
        "lfg_channel_ids": [1, 2],
        "auto_format_messages": True,
        "log_channel_id": 0,
    }
    assert filter_changed_settings_patch(row, patch) == {}


def test_filter_detects_log_channel_change() -> None:
    row = _row(log_channel_id=0)
    changed = filter_changed_settings_patch(row, {"log_channel_id": 99})
    assert changed == {"log_channel_id": 99}


def test_build_audit_summarizes_essential_fields() -> None:
    changed = {
        "log_channel_id": 555,
        "gamification_enabled": True,
        "lobby_ttl_minutes": 60,
    }
    title, description, fields = build_dashboard_settings_audit(
        changed,
        username="admin",
        user_id=123,
    )
    assert "Dashboard" in title
    assert "<@123>" in description
    assert len(fields) == 1
    body = fields[0][1]
    assert "Logs de auditoria" in body
    assert "<#555>" in body
    assert "gamificação Sim" in body
    assert "TTL" in body
    assert "log_channel_id" not in body
