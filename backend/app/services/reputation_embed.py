from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import discord

from app.db.models import Lobby


def build_lobby_reputation_request_embed(
    lobby: Lobby,
    participant_ids: list[int],
    name_for_id: dict[int, str],
) -> discord.Embed:
    lines: list[str] = []
    for user_id in participant_ids:
        label = name_for_id.get(user_id, str(user_id))
        lines.append(f"• **{label}** (`{user_id}`)")
    code = (lobby.party_code or "").strip() or "—"
    embed = discord.Embed(
        title="Reputação do grupo",
        description=(
            f"Pedido **{lobby.mode}** · código party **`{code}`**\n"
            "Reage com 👍 ou 👎 (máximo **4** votos no total).\n"
            "Cada voto aplica-se a **todas** as pessoas listadas abaixo."
        ),
        colour=discord.Colour.from_rgb(120, 200, 140),
        timestamp=datetime.now(UTC),
    )
    embed.add_field(
        name="Participantes",
        value="\n".join(lines) if lines else "_Ninguém listado._",
        inline=False,
    )
    embed.set_footer(text=f"Lobby {str(lobby.id)[:8]}…")
    return embed
