"""lobby discord_guild_id for per-guild party code checks

Revision ID: 014
Revises: 013
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lobbies",
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=True),
    )
    op.create_index("ix_lobbies_discord_guild_id", "lobbies", ["discord_guild_id"])


def downgrade() -> None:
    op.drop_index("ix_lobbies_discord_guild_id", table_name="lobbies")
    op.drop_column("lobbies", "discord_guild_id")
