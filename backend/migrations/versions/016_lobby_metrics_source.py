"""lobby create source and lifecycle timestamps for metrics

Revision ID: 016
Revises: 015
Create Date: 2026-10-15

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "lobbies",
        sa.Column(
            "create_source",
            sa.String(length=16),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "lobbies",
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "lobbies",
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_lobbies_create_source", "lobbies", ["create_source"])


def downgrade() -> None:
    op.drop_index("ix_lobbies_create_source", table_name="lobbies")
    op.drop_column("lobbies", "ended_at")
    op.drop_column("lobbies", "filled_at")
    op.drop_column("lobbies", "create_source")
