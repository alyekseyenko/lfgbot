"""leaderboard post per channel

Revision ID: 008
Revises: 007
Create Date: 2026-10-14

"""

from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("leaderboard_posts_pkey", "leaderboard_posts", type_="primary")
    op.create_primary_key(
        "leaderboard_posts_pkey",
        "leaderboard_posts",
        ["week_start", "channel_id"],
    )


def downgrade() -> None:
    op.drop_constraint("leaderboard_posts_pkey", "leaderboard_posts", type_="primary")
    op.create_primary_key("leaderboard_posts_pkey", "leaderboard_posts", ["week_start"])
