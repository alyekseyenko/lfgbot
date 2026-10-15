from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.valorant_catalog import list_agents, sync_valorant_catalog


@pytest.mark.asyncio
async def test_sync_valorant_catalog_upserts_from_mock(session: AsyncSession) -> None:
    class MockResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class MockClient:
        async def get(self, url: str, params: dict | None = None) -> MockResponse:
            if "agents" in url:
                return MockResponse(
                    {
                        "data": [
                            {
                                "uuid": "agent-1",
                                "displayName": "Jett",
                                "role": {"displayName": "Duelist"},
                                "displayIcon": "https://cdn/icon.png",
                                "fullPortrait": "https://cdn/portrait.png",
                                "abilities": [
                                    {
                                        "slot": "Ability1",
                                        "displayName": "Updraft",
                                        "displayIcon": "https://cdn/a1.png",
                                    }
                                ],
                            }
                        ]
                    }
                )
            if "competitivetiers" in url:
                return MockResponse(
                    {
                        "data": [
                            {
                                "tiers": [
                                    {
                                        "tier": 12,
                                        "tierName": "Gold 1",
                                        "smallIcon": "https://cdn/gold.png",
                                    }
                                ]
                            }
                        ]
                    }
                )
            if "playercards" in url:
                return MockResponse(
                    {
                        "data": [
                            {
                                "uuid": "card-1",
                                "displayName": "Beta Card",
                                "smallArt": "https://cdn/s.png",
                                "wideArt": "https://cdn/w.png",
                                "largeArt": "https://cdn/l.png",
                            }
                        ]
                    }
                )
            raise AssertionError(f"unexpected url {url}")

        async def aclose(self) -> None:
            return None

    async with session.begin():
        result = await sync_valorant_catalog(session, client=MockClient())  # type: ignore[arg-type]

    assert result.agents == 1
    assert result.ranks == 1
    assert result.player_cards == 1

    agents = await list_agents(session)
    assert len(agents) == 1
    assert agents[0].display_name == "Jett"
    assert len(agents[0].abilities_json) == 1
