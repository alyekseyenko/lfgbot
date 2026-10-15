from __future__ import annotations

import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select

from app.api.deps import ApiStateDep, SessionUserDep
from app.api.discord_api import exchange_code, fetch_current_user, fetch_user_guilds
from app.api.guild_cache import store_discord_guilds
from app.api.schemas import UserOut
from app.db.models import OAuthState

discord_router = APIRouter(prefix="/auth/discord", tags=["auth"])
session_router = APIRouter(prefix="/auth", tags=["auth"])


@discord_router.get("/login")
async def discord_login(request: Request, api: ApiStateDep) -> RedirectResponse:
    if not api.settings.discord_application_id:
        raise HTTPException(status_code=503, detail="DISCORD_APPLICATION_ID em falta.")
    oauth_state = secrets.token_urlsafe(32)
    async with api.session_factory() as session:
        async with session.begin():
            session.add(OAuthState(state=oauth_state))
    params = {
        "client_id": api.settings.discord_application_id,
        "redirect_uri": api.settings.oauth_redirect_uri,
        "response_type": "code",
        "scope": "identify guilds",
        "state": oauth_state,
    }
    url = f"https://discord.com/api/oauth2/authorize?{urlencode(params)}"
    return RedirectResponse(url)


@discord_router.get("/callback")
async def discord_callback(
    request: Request,
    api: ApiStateDep,
    code: str | None = None,
    oauth_state: str | None = Query(default=None, alias="state"),
) -> RedirectResponse:
    if not code or not oauth_state:
        raise HTTPException(status_code=400, detail="Parâmetros OAuth inválidos.")
    async with api.session_factory() as session:
        async with session.begin():
            result = await session.execute(
                select(OAuthState).where(OAuthState.state == oauth_state)
            )
            row = result.scalar_one_or_none()
            if row is None:
                raise HTTPException(status_code=400, detail="Estado OAuth inválido ou expirado.")
            await session.execute(delete(OAuthState).where(OAuthState.state == oauth_state))

    token_data = await exchange_code(
        client_id=api.settings.discord_application_id,
        client_secret=api.settings.discord_client_secret,
        redirect_uri=api.settings.oauth_redirect_uri,
        code=code,
    )
    access_token = str(token_data.get("access_token", ""))
    if not access_token:
        raise HTTPException(status_code=400, detail="Token Discord inválido.")
    user = await fetch_current_user(access_token)
    user_id = int(user["id"])
    try:
        guilds = await fetch_user_guilds(access_token)
        store_discord_guilds(user_id, guilds)
    except Exception:
        pass
    request.session["user"] = {
        "id": user_id,
        "username": str(user.get("username", "")),
        "avatar": user.get("avatar"),
        "access_token": access_token,
    }
    return RedirectResponse(api.settings.public_app_url)


@session_router.get("/me", response_model=UserOut)
async def auth_me(user: SessionUserDep) -> UserOut:
    return UserOut(id=str(user["id"]), username=str(user["username"]), avatar=user.get("avatar"))


@session_router.post("/logout")
async def auth_logout(request: Request) -> dict[str, str]:
    request.session.clear()
    return {"status": "ok"}
