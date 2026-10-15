import asyncio
from uuid import uuid4

import pytest

from app.bot.embed_updater import EmbedUpdateDebouncer


@pytest.mark.asyncio
async def test_debouncer_batches_ids() -> None:
    debouncer = EmbedUpdateDebouncer(interval_seconds=0.05)
    a, b = uuid4(), uuid4()
    debouncer.schedule(a)
    debouncer.schedule(b)
    debouncer.schedule(a)

    await asyncio.sleep(0.06)
    batch = await debouncer.drain()
    assert batch == {a, b}

    empty = await debouncer.drain()
    assert empty == set()
