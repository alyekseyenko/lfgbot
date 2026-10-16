"""guild guide channel + legacy stats offsets

Revision ID: 023_guild_guide_legacy_stats
Revises: 022_lfg_panel_embed_style
Create Date: 2026-10-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("guide_channel_id", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "guild_settings",
        sa.Column("guide_message_id", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "guild_settings",
        sa.Column("guide_body", sa.Text(), nullable=True),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "stats_legacy_lobbies_created",
            sa.BigInteger(),
            nullable=False,
            server_default="384931",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "stats_legacy_joins",
            sa.BigInteger(),
            nullable=False,
            server_default="1154793",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "stats_legacy_users",
            sa.BigInteger(),
            nullable=False,
            server_default="8200",
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "stats_legacy_users")
    op.drop_column("guild_settings", "stats_legacy_joins")
    op.drop_column("guild_settings", "stats_legacy_lobbies_created")
    op.drop_column("guild_settings", "guide_body")
    op.drop_column("guild_settings", "guide_message_id")
    op.drop_column("guild_settings", "guide_channel_id")
