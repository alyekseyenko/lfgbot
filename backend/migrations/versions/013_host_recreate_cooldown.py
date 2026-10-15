"""host recreate cooldown settings and user block timestamp

Revision ID: 013_host_recreate_cooldown
Revises: 012_search_penalty_settings
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("host_create_blocked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "host_recreate_cooldown_seconds",
            sa.Integer(),
            nullable=False,
            server_default="300",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "immune_host_recreate_cooldown_seconds",
            sa.Integer(),
            nullable=False,
            server_default="10",
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "immune_host_recreate_cooldown_seconds")
    op.drop_column("guild_settings", "host_recreate_cooldown_seconds")
    op.drop_column("users", "host_create_blocked_until")
