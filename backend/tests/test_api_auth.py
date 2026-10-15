import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import create_api_app
from app.core.config import Settings
from app.core.events import EventBus
from app.services.guild_config import GuildConfigService


@pytest.mark.asyncio
async def test_health_and_unauthorized_settings(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    settings = Settings(session_secret="test-secret")
    event_bus = EventBus()
    app = create_api_app(
        settings, session_factory, None, GuildConfigService(settings), event_bus
    )
    client = TestClient(app)

    assert client.get("/health/live").json() == {"status": "ok"}
    response = client.get("/guilds/1/settings")
    assert response.status_code == 401
