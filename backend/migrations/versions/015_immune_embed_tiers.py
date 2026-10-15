"""immune embed tiers (priority 1..5 per guild)

Revision ID: 015
Revises: 014
Create Date: 2026-10-15

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("immune_embed_tiers", JSONB, nullable=False, server_default="[]"),
    )
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT discord_guild_id, immune_role_ids, immune_embed_label, immune_embed_color "
            "FROM guild_settings"
        )
    ).fetchall()
    for row in rows:
        guild_id, role_ids, label, color = row
        if not role_ids:
            continue
        tier = [
            {
                "label": (label or "Pedido em destaque")[:64],
                "color": (color or "FFD700").replace("#", "")[:6],
                "role_ids": list(role_ids),
            }
        ]
        conn.execute(
            sa.text(
                "UPDATE guild_settings SET immune_embed_tiers = :tiers "
                "WHERE discord_guild_id = :gid"
            ),
            {"tiers": json.dumps(tier), "gid": guild_id},
        )


def downgrade() -> None:
    op.drop_column("guild_settings", "immune_embed_tiers")
