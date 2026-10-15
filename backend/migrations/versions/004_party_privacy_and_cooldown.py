"""party privacy and search cooldown

Revision ID: 004
Revises: 003
Create Date: 2026-10-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "lobbies",
        sa.Column("party_code_public", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "users",
        sa.Column("search_blocked_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("users", sa.Column("private_leave_day", sa.Date(), nullable=True))
    op.add_column(
        "users",
        sa.Column("private_leave_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "private_leave_count")
    op.drop_column("users", "private_leave_day")
    op.drop_column("users", "search_blocked_until")
    op.drop_column("lobbies", "party_code_public")
