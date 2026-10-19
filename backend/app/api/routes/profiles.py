from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.deps import ApiStateDep, OptionalSessionUserDep, SessionUserDep
from app.api.schemas import (
    AbilityOut,
    PlayerProfileOut,
    ProfileAgentOut,
    ProfilePatch,
    ProfileStatsOut,
    RecentCompletionOut,
)
from app.api.snowflake import parse_snowflake
from app.db.models import ValorantPlayerCard
from app.services.player_profile import build_player_profile
from app.services.riot_id import RiotIdError, parse_riot_id_field
from app.services.users import upsert_user

router = APIRouter(prefix="/profiles", tags=["profiles"])


def _profile_guild_ids(state: ApiStateDep) -> list[int]:
    return list(state.settings.discord_guild_id_list)


def _profile_to_out(view) -> PlayerProfileOut:
    return PlayerProfileOut(
        discord_id=str(view.discord_id),
        name=view.name,
        rank_label=view.rank_label,
        rank_icon_url=view.rank_icon_url,
        riot_id=view.riot_id,
        stats=ProfileStatsOut(
            level=view.stats.level,
            host_completions=view.stats.host_completions,
            player_completions=view.stats.player_completions,
            total_completions=view.stats.total_completions,
            kicks_received=view.stats.kicks_received,
            next_level_hint=view.stats.next_level_hint,
            rooms_created=view.stats.rooms_created,
            next_min_rooms=view.stats.next_min_rooms,
            creator_level_number=view.stats.creator_level_number,
        ),
        recent=[
            RecentCompletionOut(
                mode=mode,
                kind=kind,
                awarded_at=awarded_at.isoformat(),
            )
            for mode, kind, awarded_at in view.recent
        ],
        agents=[
            ProfileAgentOut(
                uuid=a.uuid,
                display_name=a.display_name,
                role_name=a.role_name,
                display_icon_url=a.display_icon_url,
                full_portrait_url=a.full_portrait_url,
                abilities=[
                    AbilityOut(
                        slot=str(ab.get("slot", "")),
                        display_name=str(ab.get("display_name", "")),
                        display_icon=ab.get("display_icon"),
                    )
                    for ab in a.abilities
                    if isinstance(ab, dict)
                ],
            )
            for a in view.agents
        ],
        player_card_uuid=view.player_card_uuid,
        player_card_wide_url=view.player_card_wide_url,
        is_self=view.is_self,
    )


@router.get("/me", response_model=PlayerProfileOut)
async def get_my_profile(
    state: ApiStateDep,
    user: SessionUserDep,
) -> PlayerProfileOut:
    viewer_id = int(user["id"])
    async with state.session_factory() as session:
        async with session.begin():
            await upsert_user(session, viewer_id, str(user.get("username", "Jogador")))
        view = await build_player_profile(
            session,
            state.bot,
            target_id=viewer_id,
            viewer_id=viewer_id,
            guild_ids=_profile_guild_ids(state),
            include_riot_id=True,
        )
    if view is None:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return _profile_to_out(view)


@router.patch("/me", response_model=PlayerProfileOut)
async def patch_my_profile(
    state: ApiStateDep,
    user: SessionUserDep,
    body: ProfilePatch,
) -> PlayerProfileOut:
    viewer_id = int(user["id"])
    async with state.session_factory() as session:
        async with session.begin():
            db_user = await upsert_user(session, viewer_id, str(user.get("username", "Jogador")))
            patch = body.model_dump(exclude_unset=True)
            if "riot_id" in patch:
                raw = (patch["riot_id"] or "").strip()
                if not raw:
                    db_user.riot_game_name = None
                    db_user.riot_tag = None
                else:
                    try:
                        name, tag = parse_riot_id_field(raw)
                    except RiotIdError as exc:
                        raise HTTPException(status_code=400, detail=str(exc)) from exc
                    db_user.riot_game_name = name
                    db_user.riot_tag = tag
            if "player_card_uuid" in patch:
                raw_card = patch["player_card_uuid"]
                if raw_card is None or not str(raw_card).strip():
                    db_user.player_card_uuid = None
                else:
                    card_uuid = str(raw_card).strip()
                    card = await session.get(ValorantPlayerCard, card_uuid)
                    if card is None:
                        raise HTTPException(
                            status_code=400,
                            detail="Player card não encontrado no catálogo.",
                        )
                    db_user.player_card_uuid = card_uuid
            await session.flush()
        view = await build_player_profile(
            session,
            state.bot,
            target_id=viewer_id,
            viewer_id=viewer_id,
            guild_ids=_profile_guild_ids(state),
            include_riot_id=True,
        )
    if view is None:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return _profile_to_out(view)


@router.get("/{discord_id}", response_model=PlayerProfileOut)
async def get_public_profile(
    discord_id: str,
    state: ApiStateDep,
    viewer: OptionalSessionUserDep,
) -> PlayerProfileOut:
    target_id = parse_snowflake(discord_id, field="discord_id")
    viewer_id = int(viewer["id"]) if viewer else None
    include_riot = viewer is not None
    async with state.session_factory() as session:
        view = await build_player_profile(
            session,
            state.bot,
            target_id=target_id,
            viewer_id=viewer_id,
            guild_ids=_profile_guild_ids(state),
            include_riot_id=include_riot,
        )
    if view is None:
        raise HTTPException(status_code=404, detail="Perfil não encontrado.")
    return _profile_to_out(view)
