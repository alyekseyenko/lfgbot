"""panel embed style separate from lobby embeds

Revision ID: 022
Revises: 021
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: str | None = "021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_panel_color",
            sa.String(length=6),
            nullable=False,
            server_default="FF4655",
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column("lfg_panel_footer_brand", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "guild_settings",
        sa.Column("lfg_panel_banner_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "guild_settings",
        sa.Column(
            "lfg_panel_decorative",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "lfg_panel_decorative")
    op.drop_column("guild_settings", "lfg_panel_banner_url")
    op.drop_column("guild_settings", "lfg_panel_footer_brand")
    op.drop_column("guild_settings", "lfg_panel_color")
