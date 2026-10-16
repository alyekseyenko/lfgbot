"""lobby post_style simple vs interactive

Revision ID: 024
Revises: 023
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "lobbies",
        sa.Column(
            "post_style",
            sa.String(length=16),
            nullable=False,
            server_default="simple",
        ),
    )
    op.execute("UPDATE lobbies SET post_style = 'interactive' WHERE post_style = 'simple'")


def downgrade() -> None:
    op.drop_column("lobbies", "post_style")
