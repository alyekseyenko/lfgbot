"""guild_settings lfg_embed_simple JSON

Revision ID: 025
Revises: 024
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("lfg_embed_simple", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "lfg_embed_simple")
