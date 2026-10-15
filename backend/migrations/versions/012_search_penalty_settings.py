"""per-guild search penalty (private leave) durations

Revision ID: 012
Revises: 011
Create Date: 2026-10-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("search_penalty_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "guild_settings",
        sa.Column("search_penalty_early_minutes", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "guild_settings",
        sa.Column("search_penalty_early_max_count", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "guild_settings",
        sa.Column("search_penalty_mid_minutes", sa.Integer(), nullable=False, server_default="15"),
    )
    op.add_column(
        "guild_settings",
        sa.Column("search_penalty_severe_hours", sa.Integer(), nullable=False, server_default="12"),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "search_penalty_severe_hours")
    op.drop_column("guild_settings", "search_penalty_mid_minutes")
    op.drop_column("guild_settings", "search_penalty_early_max_count")
    op.drop_column("guild_settings", "search_penalty_early_minutes")
    op.drop_column("guild_settings", "search_penalty_enabled")
