"""valorant catalog and riot id

Revision ID: 018
Revises: 017
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "018"
down_revision: str | None = "017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "valorant_agents",
        sa.Column("uuid", sa.String(length=64), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("role_name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("display_icon_url", sa.Text(), nullable=True),
        sa.Column("full_portrait_url", sa.Text(), nullable=True),
        sa.Column("abilities_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "valorant_ranks",
        sa.Column("tier", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("small_icon_url", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "valorant_player_cards",
        sa.Column("uuid", sa.String(length=64), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("small_art_url", sa.Text(), nullable=True),
        sa.Column("wide_art_url", sa.Text(), nullable=True),
        sa.Column("large_art_url", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_table(
        "valorant_catalog_meta",
        sa.Column("id", sa.Integer(), primary_key=True, server_default="1"),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(sa.text("INSERT INTO valorant_catalog_meta (id) VALUES (1)"))
    op.create_table(
        "guild_valorant_agent_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("discord_guild_id", sa.BigInteger(), nullable=False),
        sa.Column("agent_uuid", sa.String(length=64), nullable=False),
        sa.Column("discord_role_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["discord_guild_id"], ["guilds.discord_guild_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_uuid"], ["valorant_agents.uuid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discord_guild_id", "agent_uuid", name="uq_guild_agent_role"),
    )
    op.add_column("users", sa.Column("riot_game_name", sa.String(length=32), nullable=True))
    op.add_column("users", sa.Column("riot_tag", sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "riot_tag")
    op.drop_column("users", "riot_game_name")
    op.drop_table("guild_valorant_agent_roles")
    op.drop_table("valorant_catalog_meta")
    op.drop_table("valorant_player_cards")
    op.drop_table("valorant_ranks")
    op.drop_table("valorant_agents")
