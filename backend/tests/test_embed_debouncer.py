from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.bot.embed_updater import EmbedUpdateDebouncer, EmbedUpdater, UPDATE_EVENTS
from app.core.events import DomainEvent, EventBus, EventType


def test_first_schedule_is_immediate() -> None:
    debouncer = EmbedUpdateDebouncer(interval_seconds=2.0)
    lobby_id = uuid4()
    assert debouncer.schedule(lobby_id) is True
    assert lobby_id not in debouncer._pending


@pytest.mark.asyncio
async def test_burst_within_interval_single_pending_batch() -> None:
    debouncer = EmbedUpdateDebouncer(interval_seconds=2.0)
    lobby_id = uuid4()
    assert debouncer.schedule(lobby_id) is True
    debouncer.mark_edited(lobby_id)
    assert debouncer.schedule(lobby_id) is False
    assert debouncer.schedule(lobby_id) is False
    batch = await debouncer.drain()
    assert batch == {lobby_id}


def test_different_lobbies_both_immediate() -> None:
    debouncer = EmbedUpdateDebouncer(interval_seconds=2.0)
    lobby_a = uuid4()
    lobby_b = uuid4()
    assert debouncer.schedule(lobby_a) is True
    assert debouncer.schedule(lobby_b) is True
    assert debouncer._pending == set()


@pytest.mark.asyncio
async def test_on_event_triggers_immediate_refresh(
    session_factory, event_bus: EventBus, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import Settings
    from app.services.guild_config import GuildConfigService

    settings = Settings(embed_debounce_seconds=2.0)
    guild_config = GuildConfigService(settings)
    updater = EmbedUpdater(settings, session_factory, event_bus, guild_config)
    updater.attach()

    refreshed: list[object] = []

    async def fake_refresh(lobby_id: object) -> bool:
        refreshed.append(lobby_id)
        return True

    async def fake_refresh_and_mark(lobby_id: object) -> None:
        refreshed.append(lobby_id)

    monkeypatch.setattr(updater, "_refresh_and_mark", fake_refresh_and_mark)

    lobby_id = uuid4()
    await event_bus.publish(DomainEvent(EventType.member_joined, lobby_id))
    await asyncio.sleep(0.05)
    assert refreshed == [lobby_id]


def test_lobby_created_not_in_update_events() -> None:
    assert EventType.lobby_created not in UPDATE_EVENTS
