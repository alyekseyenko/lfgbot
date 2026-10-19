"""party_code_max_length on guild_settings

Revision ID: 029
Revises: 028
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "party_code_max_length",
            sa.Integer(),
            nullable=False,
            server_default="6",
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "party_code_max_length")
