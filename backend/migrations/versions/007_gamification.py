"""gamification lobby_completions

Revision ID: 007
Revises: 006
Create Date: 2026-10-14

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lobby_completions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lobby_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column(
            "awarded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lobby_id"], ["lobbies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.discord_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lobby_id", "user_id", "kind", name="uq_lobby_completion"),
        sa.CheckConstraint("kind IN ('host', 'player')", name="ck_lobby_completion_kind"),
    )
    op.create_index("ix_lobby_completions_user_awarded", "lobby_completions", ["user_id", "awarded_at"])

    op.create_table(
        "leaderboard_posts",
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint("week_start"),
    )


def downgrade() -> None:
    op.drop_table("leaderboard_posts")
    op.drop_index("ix_lobby_completions_user_awarded", table_name="lobby_completions")
    op.drop_table("lobby_completions")
