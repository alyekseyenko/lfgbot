from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ValorantPlayerCard
from app.services.player_profile import build_player_profile
from app.services.users import upsert_user


@pytest.mark.asyncio
async def test_profile_uses_chosen_player_card(session: AsyncSession) -> None:
    session.add(
        ValorantPlayerCard(
            uuid="card-test-1",
            display_name="Test Card",
            wide_art_url="https://cdn.example/wide.png",
            synced_at=datetime.now(UTC),
        )
    )
    user = await upsert_user(session, 2001, "CardUser")
    user.player_card_uuid = "card-test-1"
    await session.flush()

    view = await build_player_profile(
        session,
        None,
        target_id=2001,
        viewer_id=2001,
        guild_ids=[],
        include_riot_id=False,
    )
    assert view is not None
    assert view.player_card_uuid == "card-test-1"
    assert view.player_card_wide_url == "https://cdn.example/wide.png"
