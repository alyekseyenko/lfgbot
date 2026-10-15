from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    discord_token: str = ""
    discord_application_id: str = ""
    discord_guild_id: int = 0
    discord_guild_ids: str = ""
    lfg_channel_ids: str = ""

    database_url: str = "postgresql+asyncpg://lfg:lfg@localhost:5432/lfg"
    log_level: str = "INFO"

    lobby_ttl_minutes: int = 45
    expire_poll_seconds: int = 30
    embed_debounce_seconds: float = 2.0
    expired_mode: Literal["edit", "delete"] = "edit"
    auto_format_messages: bool = True
    default_lfg_mode: Literal["Competitivo", "Unrated"] = "Competitivo"
    embed_thumbnail_url: str = ""

    gamification_enabled: bool = False
    stats_channel_id: int = 0
    completion_min_seconds: int = 180

    panel_sticky_enabled: bool = True
    panel_sticky_cooldown_seconds: float = 30.0

    @field_validator("discord_guild_id", mode="before")
    @classmethod
    def empty_guild_id(cls, value: object) -> object:
        if value == "" or value is None:
            return 0
        return value

    def stats_post_channel_ids(self) -> list[int]:
        """Canais do ranking automático: STATS_CHANNEL_ID ou, se 0, todos os LFG."""
        if self.stats_channel_id:
            return [self.stats_channel_id]
        return self.lfg_channel_id_list

    @property
    def lfg_channel_id_list(self) -> list[int]:
        if not self.lfg_channel_ids.strip():
            return []
        return [int(part.strip()) for part in self.lfg_channel_ids.split(",") if part.strip()]

    @property
    def discord_guild_id_list(self) -> list[int]:
        ids: list[int] = []
        if self.discord_guild_ids.strip():
            ids.extend(
                int(part.strip()) for part in self.discord_guild_ids.split(",") if part.strip()
            )
        elif self.discord_guild_id:
            ids.append(self.discord_guild_id)
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
