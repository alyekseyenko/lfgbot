"""reputation_enabled_at on guild_settings

Revision ID: 032
Revises: 031
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("reputation_enabled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE guild_settings
            SET reputation_enabled_at = (NOW() AT TIME ZONE 'utc')
            WHERE reputation_channel_id > 0 AND reputation_enabled_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "reputation_enabled_at")
