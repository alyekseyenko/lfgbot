import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class LobbyState(str, enum.Enum):
    open = "open"
    full = "full"
    closed = "closed"
    expired = "expired"


class User(Base):
    __tablename__ = "users"

    discord_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    rank: Mapped[str | None] = mapped_column(String(64), nullable=True)
    search_blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    private_leave_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    private_leave_count: Mapped[int] = mapped_column(nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    hosted_lobbies: Mapped[list["Lobby"]] = relationship(back_populates="host")
    lobby_memberships: Mapped[list["LobbyMember"]] = relationship(back_populates="user")


class Lobby(Base):
    __tablename__ = "lobbies"
    __table_args__ = (CheckConstraint("slots >= 1 AND slots <= 4", name="ck_lobbies_slots"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
