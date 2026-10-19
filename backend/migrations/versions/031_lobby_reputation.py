"""lobby reputation settings and vote tables

Revision ID: 031
Revises: 030
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("reputation_channel_id", sa.BigInteger(), nullable=False, server_default="0"),
    )
    op.add_column(
        "guild_settings",
        sa.Column("reputation_delay_minutes", sa.Integer(), nullable=False, server_default="50"),
    )
    op.create_table(
        "lobby_reputation_posts",
        sa.Column("lobby_id", UUID(as_uuid=True), sa.ForeignKey("lobbies.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("channel_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "posted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_table(
        "lobby_reputation_votes",
        sa.Column("lobby_id", UUID(as_uuid=True), sa.ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "voter_id",
            sa.BigInteger(),
            sa.ForeignKey("users.discord_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("value IN (-1, 1)", name="ck_lobby_reputation_vote_value"),
        sa.PrimaryKeyConstraint("lobby_id", "voter_id", name="pk_lobby_reputation_votes"),
    )


def downgrade() -> None:
    op.drop_table("lobby_reputation_votes")
    op.drop_table("lobby_reputation_posts")
    op.drop_column("guild_settings", "reputation_delay_minutes")
    op.drop_column("guild_settings", "reputation_channel_id")
