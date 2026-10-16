import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LobbyState(str, enum.Enum):
    open = "open"
    full = "full"
    closed = "closed"
    expired = "expired"


class Guild(Base):
    __tablename__ = "guilds"

    discord_guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    bot_removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    settings: Mapped["GuildSettings | None"] = relationship(back_populates="guild", uselist=False)
    role_mappings: Mapped[list["GuildRoleMapping"]] = relationship(back_populates="guild")
    valorant_agent_roles: Mapped[list["GuildValorantAgentRole"]] = relationship(
        back_populates="guild"
    )


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    discord_guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.discord_guild_id", ondelete="CASCADE"), primary_key=True
    )
    lfg_channel_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, server_default="[]")
    announce_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    auto_format_messages: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    default_lfg_mode: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="Competitivo"
    )
    gamification_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    stats_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    log_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    guide_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    guide_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    guide_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    stats_legacy_lobbies_created: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="384931"
    )
    stats_legacy_joins: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="1154793"
    )
    stats_legacy_users: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="8200"
    )
    panel_sticky_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lobby_ttl_minutes: Mapped[int] = mapped_column(Integer, nullable=False, server_default="45")
    immune_role_ids: Mapped[list[int]] = mapped_column(JSONB, nullable=False, server_default="[]")
    lfg_embed_color_source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="mode"
    )
    rank_embed_colors: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    lfg_embed_competitive_color: Mapped[str] = mapped_column(
        String(6), nullable=False, server_default="FF4655"
    )
    lfg_embed_unrated_color: Mapped[str] = mapped_column(
        String(6), nullable=False, server_default="5E98D9"
    )
    lfg_embed_full_color: Mapped[str] = mapped_column(
        String(6), nullable=False, server_default="C23B22"
    )
    lfg_embed_inactive_color: Mapped[str] = mapped_column(
        String(6), nullable=False, server_default="4A4E5A"
    )
    lfg_embed_decorative: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lfg_embed_footer_brand: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="LFG Valorant"
    )
    lfg_embed_banner_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    lfg_embed_custom_texts: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    lfg_embed_show_author: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lfg_embed_show_timestamp: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lfg_embed_show_thumbnail: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lfg_embed_banner_on_panel: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lfg_embed_banner_on_lobby: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lfg_panel_thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    lfg_panel_color: Mapped[str] = mapped_column(
        String(6), nullable=False, server_default="FF4655"
    )
    lfg_panel_footer_brand: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lfg_panel_banner_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    lfg_panel_decorative: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    lfg_embed_thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    lfg_embed_simple: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    immune_embed_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    immune_embed_color: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default="FFD700"
    )
    immune_embed_label: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default="Pedido em destaque"
    )
    immune_embed_tiers: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    search_penalty_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    search_penalty_early_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="5"
    )
    search_penalty_early_max_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="3"
    )
    search_penalty_mid_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="15"
    )
    search_penalty_severe_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="12"
    )
    host_recreate_cooldown_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="300"
    )
    immune_host_recreate_cooldown_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="10"
    )

    guild: Mapped[Guild] = relationship(back_populates="settings")


class GuildRoleMapping(Base):
    __tablename__ = "guild_role_mappings"
    __table_args__ = (
        UniqueConstraint(
            "discord_guild_id",
            "mapping_type",
            "logical_key",
            name="uq_guild_role_mapping",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.discord_guild_id", ondelete="CASCADE"), nullable=False
    )
    mapping_type: Mapped[str] = mapped_column(String(32), nullable=False)
    logical_key: Mapped[str] = mapped_column(String(64), nullable=False)
    discord_role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    guild: Mapped[Guild] = relationship(back_populates="role_mappings")


class OAuthState(Base):
    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class User(Base):
    __tablename__ = "users"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    search_blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    host_create_blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    private_leave_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    private_leave_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    riot_game_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    riot_tag: Mapped[str | None] = mapped_column(String(8), nullable=True)
    player_card_uuid: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("valorant_player_cards.uuid", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    hosted_lobbies: Mapped[list["Lobby"]] = relationship(back_populates="host")
    lobby_memberships: Mapped[list["LobbyMember"]] = relationship(back_populates="user")


class Lobby(Base):
    __tablename__ = "lobbies"
    __table_args__ = (CheckConstraint("slots >= 1 AND slots <= 4", name="ck_lobbies_slots"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    discord_guild_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    host_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.discord_id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    slots: Mapped[int] = mapped_column(nullable=False)
    party_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    party_code_public: Mapped[bool] = mapped_column(nullable=False, server_default="true")
    min_rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    max_rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ranks_verified: Mapped[bool] = mapped_column(nullable=False, server_default="false")
    wanted_agents: Mapped[str | None] = mapped_column(String(128), nullable=True)
    state: Mapped[LobbyState] = mapped_column(
        Enum(LobbyState, name="lobby_state", native_enum=False),
        nullable=False,
        default=LobbyState.open,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    create_source: Mapped[str] = mapped_column(String(16), nullable=False, server_default="unknown")
    post_style: Mapped[str] = mapped_column(String(16), nullable=False, server_default="simple")
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    host: Mapped[User] = relationship(back_populates="hosted_lobbies")
    members: Mapped[list["LobbyMember"]] = relationship(back_populates="lobby")


class CompletionKind(str, enum.Enum):
    host = "host"
    player = "player"


class LobbyCompletion(Base):
    __tablename__ = "lobby_completions"
    __table_args__ = (
        CheckConstraint("kind IN ('host', 'player')", name="ck_lobby_completion_kind"),
        Index("ix_lobby_completions_user_awarded", "user_id", "awarded_at"),
        UniqueConstraint("lobby_id", "user_id", "kind", name="uq_lobby_completion"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lobby_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.discord_id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LeaderboardPost(Base):
    __tablename__ = "leaderboard_posts"

    week_start: Mapped[date] = mapped_column(Date, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class LfgPanelPost(Base):
    __tablename__ = "lfg_panel_posts"

    channel_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)


class LobbyMember(Base):
    __tablename__ = "lobby_members"
    __table_args__ = (
        Index(
            "uq_lobby_member_active",
            "lobby_id",
            "user_id",
            unique=True,
            postgresql_where=text("left_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    lobby_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.discord_id"), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leave_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    lobby: Mapped[Lobby] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="lobby_memberships")


class ValorantAgent(Base):
    __tablename__ = "valorant_agents"

    uuid: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role_name: Mapped[str] = mapped_column(String(64), nullable=False, server_default="")
    display_icon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    full_portrait_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    abilities_json: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ValorantRank(Base):
    __tablename__ = "valorant_ranks"

    tier: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    small_icon_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ValorantPlayerCard(Base):
    __tablename__ = "valorant_player_cards"

    uuid: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    small_art_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    wide_art_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    large_art_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ValorantCatalogMeta(Base):
    __tablename__ = "valorant_catalog_meta"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, server_default="1")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GuildValorantAgentRole(Base):
    __tablename__ = "guild_valorant_agent_roles"
    __table_args__ = (
        UniqueConstraint("discord_guild_id", "agent_uuid", name="uq_guild_agent_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    discord_guild_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("guilds.discord_guild_id", ondelete="CASCADE"), nullable=False
    )
    agent_uuid: Mapped[str] = mapped_column(
        String(64), ForeignKey("valorant_agents.uuid", ondelete="CASCADE"), nullable=False
    )
    discord_role_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    guild: Mapped[Guild] = relationship(back_populates="valorant_agent_roles")
