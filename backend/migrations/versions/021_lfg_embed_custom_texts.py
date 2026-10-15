"""lfg embed custom texts and display flags

Revision ID: 021
Revises: 020
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "021"
down_revision: str | None = "020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("lfg_embed_custom_texts", JSONB, nullable=False, server_default="{}"),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_show_author",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_show_timestamp",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_show_thumbnail",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_banner_on_panel",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_embed_banner_on_lobby",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column("lfg_panel_thumbnail_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "guild_settings",
        sa.Column("lfg_embed_thumbnail_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "lfg_embed_thumbnail_url")
    op.drop_column("guild_settings", "lfg_panel_thumbnail_url")
    op.drop_column("guild_settings", "lfg_embed_banner_on_lobby")
    op.drop_column("guild_settings", "lfg_embed_banner_on_panel")
    op.drop_column("guild_settings", "lfg_embed_show_thumbnail")
    op.drop_column("guild_settings", "lfg_embed_show_timestamp")
    op.drop_column("guild_settings", "lfg_embed_show_author")
    op.drop_column("guild_settings", "lfg_embed_custom_texts")
