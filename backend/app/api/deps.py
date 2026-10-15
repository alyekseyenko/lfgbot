from __future__ import annotations

from typing import Annotated

import discord
from fastapi import Depends, HTTPException, Request

from app.api.state import ApiState


def get_api_state(request: Request) -> ApiState:
    state = getattr(request.app.state, "api_state", None)
    if state is None:
        raise HTTPException(status_code=503, detail="API não inicializada.")
    return state


ApiStateDep = Annotated[ApiState, Depends(get_api_state)]


def require_session_user(request: Request) -> dict:
    user = request.session.get("user")
    if not user:
        raise HTTPException(status_code=401, detail="Inicia sessão com Discord.")
    return user


SessionUserDep = Annotated[dict, Depends(require_session_user)]


def optional_session_user(request: Request) -> dict | None:
    user = request.session.get("user")
    if user:
        return user
    return None


OptionalSessionUserDep = Annotated[dict | None, Depends(optional_session_user)]


def require_bot(state: ApiStateDep) -> discord.Client:
    if state.bot is None:
        raise HTTPException(status_code=503, detail="Bot Discord indisponível.")
    return state.bot


BotDep = Annotated[discord.Client, Depends(require_bot)]
