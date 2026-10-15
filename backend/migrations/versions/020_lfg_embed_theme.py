"""lfg embed theme settings

Revision ID: 020
Revises: 019
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: str | None = "019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_competitive_color",
            sa.String(length=6),
            nullable=False,
            server_default="FF4655",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_unrated_color",
            sa.String(length=6),
            nullable=False,
            server_default="5E98D9",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_full_color",
            sa.String(length=6),
            nullable=False,
            server_default="C23B22",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_inactive_color",
            sa.String(length=6),
            nullable=False,
            server_default="4A4E5A",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_decorative",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_footer_brand",
            sa.String(length=64),
            nullable=False,
            server_default="LFG Valorant",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column("lfg_embed_banner_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "lfg_embed_banner_url")
    op.drop_column("guild_settings", "lfg_embed_footer_brand")
    op.drop_column("guild_settings", "lfg_embed_decorative")
    op.drop_column("guild_settings", "lfg_embed_inactive_color")
    op.drop_column("guild_settings", "lfg_embed_full_color")
    op.drop_column("guild_settings", "lfg_embed_unrated_color")
    op.drop_column("guild_settings", "lfg_embed_competitive_color")
