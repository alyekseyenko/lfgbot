from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import ApiStateDep, SessionUserDep
from app.api.routes.guilds import _assert_manage_guild, _primary_manage_guild_id
from app.api.schemas import (
    AbilityOut,
    CatalogMetaOut,
    CatalogSyncOut,
    ValorantAgentOut,
    ValorantPlayerCardOut,
    ValorantRankOut,
)
from app.services.valorant_catalog import (
    get_catalog_meta,
    list_agents,
    list_player_cards,
    list_ranks,
    sync_valorant_catalog,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _agent_out(agent) -> ValorantAgentOut:
    abilities = [
        AbilityOut(
            slot=str(a.get("slot", "")),
            display_name=str(a.get("display_name", "")),
            display_icon=a.get("display_icon"),
        )
        for a in (agent.abilities_json or [])
        if isinstance(a, dict)
    ]
    return ValorantAgentOut(
        uuid=agent.uuid,
        display_name=agent.display_name,
        role_name=agent.role_name,
        display_icon_url=agent.display_icon_url,
        full_portrait_url=agent.full_portrait_url,
        abilities=abilities,
    )


@router.get("/meta", response_model=CatalogMetaOut)
async def catalog_meta(state: ApiStateDep) -> CatalogMetaOut:
    async with state.session_factory() as session:
        last = await get_catalog_meta(session)
    return CatalogMetaOut(last_synced_at=last.isoformat() if last else None)


@router.get("/agents", response_model=list[ValorantAgentOut])
async def catalog_agents(state: ApiStateDep) -> list[ValorantAgentOut]:
    async with state.session_factory() as session:
        agents = await list_agents(session)
    return [_agent_out(a) for a in agents]


@router.get("/ranks", response_model=list[ValorantRankOut])
async def catalog_ranks(state: ApiStateDep) -> list[ValorantRankOut]:
    async with state.session_factory() as session:
        ranks = await list_ranks(session)
    return [
        ValorantRankOut(
            tier=r.tier,
            display_name=r.display_name,
            small_icon_url=r.small_icon_url,
        )
        for r in ranks
    ]


@router.get("/player-cards", response_model=list[ValorantPlayerCardOut])
async def catalog_player_cards(state: ApiStateDep) -> list[ValorantPlayerCardOut]:
    async with state.session_factory() as session:
        cards = await list_player_cards(session)
    return [
        ValorantPlayerCardOut(
            uuid=c.uuid,
            display_name=c.display_name,
            small_art_url=c.small_art_url,
            wide_art_url=c.wide_art_url,
            large_art_url=c.large_art_url,
        )
        for c in cards
    ]


@router.post("/sync", response_model=CatalogSyncOut)
async def catalog_sync(state: ApiStateDep, user: SessionUserDep) -> CatalogSyncOut:
    gid = _primary_manage_guild_id(state)
    if gid is None:
        raise HTTPException(status_code=400, detail="Nenhum servidor configurado.")
    await _assert_manage_guild(user, gid)
    async with state.session_factory() as session:
        async with session.begin():
            result = await sync_valorant_catalog(session)
    return CatalogSyncOut(
        agents=result.agents,
        ranks=result.ranks,
        player_cards=result.player_cards,
    )
