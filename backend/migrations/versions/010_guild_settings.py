"""guilds, guild_settings, guild_role_mappings, oauth_states

Revision ID: 010
Revises: 009
Create Date: 2026-10-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guilds",
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False, server_default=""),
        sa.Column(
            "installed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("bot_removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("discord_guild_id"),
    )
    op.create_table(
        "guild_settings",
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "lfg_channel_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.Column("announce_channel_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "auto_format_messages",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column(
            "default_lfg_mode",
            sa.String(length=32),
            server_default="Competitivo",
            nullable=False,
        ),
        sa.Column(
            "gamification_enabled",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
        sa.Column("stats_channel_id", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "panel_sticky_enabled",
            sa.Boolean(),
            server_default="true",
            nullable=False,
        ),
        sa.Column("lobby_ttl_minutes", sa.Integer(), server_default="45", nullable=False),
        sa.Column(
            "immune_role_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="[]",
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["discord_guild_id"], ["guilds.discord_guild_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("discord_guild_id"),
    )
    op.create_table(
        "guild_role_mappings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column("mapping_type", sa.String(length=32), nullable=False),
        sa.Column("logical_key", sa.String(length=64), nullable=False),
        sa.Column("discord_role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["discord_guild_id"], ["guilds.discord_guild_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "discord_guild_id",
            "mapping_type",
            "logical_key",
            name="uq_guild_role_mapping",
        ),
    )
    op.create_table(
        "oauth_states",
        sa.Column("state", sa.String(length=128), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("state"),
    )


def downgrade() -> None:
    op.drop_table("oauth_states")
    op.drop_table("guild_role_mappings")
    op.drop_table("guild_settings")
    op.drop_table("guilds")
