from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ValorantAgent, ValorantCatalogMeta, ValorantPlayerCard, ValorantRank

logger = logging.getLogger(__name__)

BASE_URL = "https://valorant-api.com/v1"


class CatalogSyncResult:
    def __init__(self) -> None:
        self.agents = 0
        self.ranks = 0
        self.player_cards = 0


def _ability_rows(agent: dict[str, Any]) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []
    for slot in agent.get("abilities") or []:
        if not isinstance(slot, dict):
            continue
        out.append(
            {
                "slot": str(slot.get("slot", "")),
                "display_name": str(slot.get("displayName", "")),
                "display_icon": slot.get("displayIcon"),
            }
        )
    return out[:4]


async def sync_valorant_catalog(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient | None = None,
) -> CatalogSyncResult:
    result = CatalogSyncResult()
    own_client = client is None
    if own_client:
        client = httpx.AsyncClient(timeout=60.0)
    try:
        assert client is not None
        now = datetime.now(UTC)

        agents_resp = await client.get(f"{BASE_URL}/agents", params={"isPlayableCharacter": True})
        agents_resp.raise_for_status()
        for item in agents_resp.json().get("data") or []:
            if not isinstance(item, dict) or not item.get("uuid"):
                continue
            uuid = str(item["uuid"])
            stmt = insert(ValorantAgent).values(
                uuid=uuid,
                display_name=str(item.get("displayName", "")),
                role_name=str((item.get("role") or {}).get("displayName", "")),
                display_icon_url=item.get("displayIcon"),
                full_portrait_url=item.get("fullPortrait") or item.get("displayIconFull"),
                abilities_json=_ability_rows(item),
                synced_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ValorantAgent.uuid],
                set_={
                    "display_name": stmt.excluded.display_name,
                    "role_name": stmt.excluded.role_name,
                    "display_icon_url": stmt.excluded.display_icon_url,
                    "full_portrait_url": stmt.excluded.full_portrait_url,
                    "abilities_json": stmt.excluded.abilities_json,
                    "synced_at": stmt.excluded.synced_at,
                },
            )
            await session.execute(stmt)
            result.agents += 1

        tiers_resp = await client.get(f"{BASE_URL}/competitivetiers")
        tiers_resp.raise_for_status()
        episodes = tiers_resp.json().get("data") or []
        latest = episodes[-1] if episodes else {}
        for tier in latest.get("tiers") or []:
            if not isinstance(tier, dict):
                continue
            tier_num = int(tier.get("tier", -1))
            if tier_num < 0:
                continue
            stmt = insert(ValorantRank).values(
                tier=tier_num,
                display_name=str(tier.get("tierName", "")),
                small_icon_url=tier.get("smallIcon"),
                synced_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ValorantRank.tier],
                set_={
                    "display_name": stmt.excluded.display_name,
                    "small_icon_url": stmt.excluded.small_icon_url,
                    "synced_at": stmt.excluded.synced_at,
                },
            )
            await session.execute(stmt)
            result.ranks += 1

        cards_resp = await client.get(f"{BASE_URL}/playercards")
        cards_resp.raise_for_status()
        for card in cards_resp.json().get("data") or []:
            if not isinstance(card, dict) or not card.get("uuid"):
                continue
            uuid = str(card["uuid"])
            stmt = insert(ValorantPlayerCard).values(
                uuid=uuid,
                display_name=str(card.get("displayName", "")),
                small_art_url=card.get("smallArt"),
                wide_art_url=card.get("wideArt"),
                large_art_url=card.get("largeArt"),
                synced_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ValorantPlayerCard.uuid],
                set_={
                    "display_name": stmt.excluded.display_name,
                    "small_art_url": stmt.excluded.small_art_url,
                    "wide_art_url": stmt.excluded.wide_art_url,
                    "large_art_url": stmt.excluded.large_art_url,
                    "synced_at": stmt.excluded.synced_at,
                },
            )
            await session.execute(stmt)
            result.player_cards += 1

        meta = await session.get(ValorantCatalogMeta, 1)
        if meta is None:
            meta = ValorantCatalogMeta(id=1, last_synced_at=now)
            session.add(meta)
        else:
            meta.last_synced_at = now
        await session.flush()
        logger.info(
            "valorant catalog synced: %s agents, %s ranks, %s cards",
            result.agents,
            result.ranks,
            result.player_cards,
        )
        return result
    finally:
        if own_client and client is not None:
            await client.aclose()


async def get_catalog_meta(session: AsyncSession) -> datetime | None:
    meta = await session.get(ValorantCatalogMeta, 1)
    return meta.last_synced_at if meta else None


async def list_agents(session: AsyncSession) -> list[ValorantAgent]:
    result = await session.execute(select(ValorantAgent).order_by(ValorantAgent.display_name.asc()))
    return list(result.scalars())


async def list_ranks(session: AsyncSession) -> list[ValorantRank]:
    result = await session.execute(select(ValorantRank).order_by(ValorantRank.tier.asc()))
    return list(result.scalars())


async def list_player_cards(session: AsyncSession) -> list[ValorantPlayerCard]:
    result = await session.execute(
        select(ValorantPlayerCard).order_by(ValorantPlayerCard.display_name.asc())
    )
    return list(result.scalars())
