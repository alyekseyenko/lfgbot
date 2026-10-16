from __future__ import annotations

import os
from pathlib import Path

import discord
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes import auth as auth_routes
from app.api.routes import catalog as catalog_routes
from app.api.routes import guilds
from app.api.routes import health as health_routes
from app.api.routes import profiles as profiles_routes
from app.api.state import ApiState
from app.core.config import Settings
from app.core.events import EventBus
from app.core.metrics import metrics_payload
from app.services.guild_config import GuildConfigService


def create_api_app(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    bot: discord.Client | None,
    guild_config: GuildConfigService,
    event_bus: EventBus,
) -> FastAPI:
    app = FastAPI(title="LFG Valorant Dashboard", version="0.1.0")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        same_site="lax",
        https_only=False,
    )
    origins = {
        settings.public_app_url.rstrip("/"),
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5190",
        "http://127.0.0.1:5190",
    }
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.api_state = ApiState(
        settings=settings,
        session_factory=session_factory,
        bot=bot,
        guild_config=guild_config,
        event_bus=event_bus,
    )
    app.include_router(auth_routes.discord_router)
    app.include_router(auth_routes.session_router)
    app.include_router(guilds.router)
    app.include_router(catalog_routes.router)
    app.include_router(profiles_routes.router)
    app.include_router(health_routes.router)

    @app.get("/health")
    async def health_legacy() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/metrics")
    async def metrics() -> Response:
        body, content_type = metrics_payload()
        return Response(content=body, media_type=content_type)

    static_candidates: list[Path] = []
    spa_env = os.environ.get("SPA_STATIC_DIR", "").strip()
    if spa_env:
        static_candidates.append(Path(spa_env))
    static_candidates.append(Path(__file__).resolve().parents[3] / "frontend" / "dist")
    static_dir = next((p for p in static_candidates if p.is_dir()), None)
    if static_dir is not None:
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa-assets")

        @app.get("/{full_path:path}")
        async def spa_file_or_index(full_path: str) -> FileResponse:
            if not full_path:
                return FileResponse(static_dir / "index.html")
            candidate = (static_dir / full_path).resolve()
            try:
                candidate.relative_to(static_dir.resolve())
            except ValueError:
                raise HTTPException(status_code=404, detail="Not found") from None
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(static_dir / "index.html")

    return app
