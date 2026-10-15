"""lfg embed colours and immune highlight settings

Revision ID: 011
Revises: 010
Create Date: 2026-10-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_color_source",
            sa.String(length=32),
            nullable=False,
            server_default="mode",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "rank_embed_colors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "immune_embed_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "immune_embed_color",
            sa.String(length=7),
            nullable=False,
            server_default="FFD700",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "immune_embed_label",
            sa.String(length=64),
            nullable=False,
            server_default="Pedido em destaque",
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "immune_embed_label")
    op.drop_column("guild_settings", "immune_embed_color")
    op.drop_column("guild_settings", "immune_embed_enabled")
    op.drop_column("guild_settings", "rank_embed_colors")
    op.drop_column("guild_settings", "lfg_embed_color_source")
