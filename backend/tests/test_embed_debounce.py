from uuid import uuid4

import pytest

from app.bot.embed_updater import EmbedUpdateDebouncer


@pytest.mark.asyncio
async def test_debouncer_batches_ids() -> None:
    debouncer = EmbedUpdateDebouncer(interval_seconds=0.05)
    a, b = uuid4(), uuid4()
    debouncer.mark_edited(a)
    debouncer.mark_edited(b)
    assert debouncer.schedule(a) is False
    assert debouncer.schedule(b) is False
    assert debouncer.schedule(a) is False

    batch = await debouncer.drain()
    assert batch == {a, b}

    empty = await debouncer.drain()
    assert empty == set()
