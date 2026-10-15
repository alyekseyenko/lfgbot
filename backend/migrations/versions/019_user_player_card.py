"""user player card choice

Revision ID: 019
Revises: 018
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: str | None = "018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("player_card_uuid", sa.String(length=64), nullable=True),
    )
    op.create_foreign_key(
        "fk_users_player_card_uuid",
        "users",
        "valorant_player_cards",
        ["player_card_uuid"],
        ["uuid"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_player_card_uuid", "users", type_="foreignkey")
    op.drop_column("users", "player_card_uuid")
