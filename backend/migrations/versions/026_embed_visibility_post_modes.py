"""guild post mode flags and detailed embed visibility JSON

Revision ID: 026
Revises: 025
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "026"
down_revision = "025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_post_style_simple_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_post_style_detailed_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column("lfg_embed_detailed", JSONB, nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "lfg_embed_detailed")
    op.drop_column("guild_settings", "lfg_post_style_detailed_enabled")
    op.drop_column("guild_settings", "lfg_post_style_simple_enabled")
