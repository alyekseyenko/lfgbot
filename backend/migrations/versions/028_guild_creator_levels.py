"""guild_creator_levels (rooms created ranks)

Revision ID: 028
Revises: 027
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guild_creator_levels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column("level_number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("min_rooms", sa.Integer(), nullable=False),
        sa.Column("discord_role_id", sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(
            ["discord_guild_id"],
            ["guilds.discord_guild_id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "discord_guild_id",
            "level_number",
            name="uq_guild_creator_level_number",
        ),
        sa.CheckConstraint(
            "level_number >= 1 AND level_number <= 20",
            name="ck_creator_level_number",
        ),
        sa.CheckConstraint("min_rooms >= 0", name="ck_creator_level_min_rooms"),
    )
    op.create_index(
        "ix_guild_creator_levels_guild_rooms",
        "guild_creator_levels",
        ["discord_guild_id", "min_rooms"],
    )
    op.create_index(
        "ix_lobbies_guild_host",
        "lobbies",
        ["discord_guild_id", "host_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_lobbies_guild_host", table_name="lobbies")
    op.drop_index("ix_guild_creator_levels_guild_rooms", table_name="guild_creator_levels")
    op.drop_table("guild_creator_levels")
