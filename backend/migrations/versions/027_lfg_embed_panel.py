"""panel embed visibility JSON

Revision ID: 027
Revises: 026
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("lfg_embed_panel", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "lfg_embed_panel")
