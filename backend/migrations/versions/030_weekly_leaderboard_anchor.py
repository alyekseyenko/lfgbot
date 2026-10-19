"""weekly_leaderboard_anchor on guild_settings

Revision ID: 030
Revises: 029
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("weekly_leaderboard_anchor", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "weekly_leaderboard_anchor")
