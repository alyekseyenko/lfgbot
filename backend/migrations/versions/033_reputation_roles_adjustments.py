"""reputation role thresholds and manual adjustments

Revision ID: 033
Revises: 032
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "reputation_negative_threshold",
            sa.Integer(),
            nullable=False,
            server_default="-15",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "reputation_negative_role_id",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "reputation_positive_threshold",
            sa.Integer(),
            nullable=False,
            server_default="25",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "reputation_positive_role_id",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_table(
        "guild_reputation_adjustments",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("delta", sa.Integer(), nullable=False),
        sa.Column("created_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["discord_guild_id"],
            ["guilds.discord_guild_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.discord_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.discord_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_guild_reputation_adjustments_guild_user",
        "guild_reputation_adjustments",
        ["discord_guild_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_guild_reputation_adjustments_guild_user",
        table_name="guild_reputation_adjustments",
    )
    op.drop_table("guild_reputation_adjustments")
    op.drop_column("guild_settings", "reputation_positive_role_id")
    op.drop_column("guild_settings", "reputation_positive_threshold")
    op.drop_column("guild_settings", "reputation_negative_role_id")
    op.drop_column("guild_settings", "reputation_negative_threshold")
