"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-22

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("discord_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("rank", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("discord_id"),
    )
    op.create_table(
        "lobbies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("host_id", sa.BigInteger(), nullable=False),
        sa.Column("mode", sa.String(length=32), nullable=False),
        sa.Column("slots", sa.Integer(), nullable=False),
        sa.Column("party_code", sa.String(length=128), nullable=True),
        sa.Column(
            "state",
            sa.Enum("open", "full", "closed", "expired", name="lobby_state", native_enum=False),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=True),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("slots >= 1 AND slots <= 4", name="ck_lobbies_slots"),
        sa.ForeignKeyConstraint(["host_id"], ["users.discord_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "lobby_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lobby_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("leave_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lobby_id"], ["lobbies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.discord_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_lobby_member_active",
        "lobby_members",
        ["lobby_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("left_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_lobby_member_active", table_name="lobby_members")
    op.drop_table("lobby_members")
    op.drop_table("lobbies")
    op.drop_table("users")
