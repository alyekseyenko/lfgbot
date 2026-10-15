from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.discord_roles import extract_rank_bounds_from_roles, extract_wanted_agents_from_roles
from app.bot.gamification_roles import sync_member_lfg_roles
from app.bot.members import upsert_user_from_member
from app.bot.lobby_create import LobbyCreateParams, begin_lobby_create
from app.bot.message_parser import parse_lfg_message
from app.core.config import Settings
from app.core.events import EventBus
from app.services import lobbies as lobby_service
from app.services.errors import LobbyEditError, LobbyNotJoinableError, RankRangeError
from app.services.lobby_patch import UNSET, LobbyHostPatch
from app.bot.embeds import allowed_mentions_for_roles
from app.bot.gamification_tasks import weekly_leaderboard_embed
from app.bot.lfg_panel import notify_panel_sticky_activity, publish_panel_message_bound
from app.bot.profile_embed import build_profile_embed
from app.db.models import User
from app.services.gamification import last_completion_at, profile_stats, recent_completions
from app.services.ranks import AGENT_ROLES, VALORANT_RANKS

logger = logging.getLogger(__name__)

RANK_CHOICES = [
    app_commands.Choice(name=rank, value=rank)
    for rank in VALORANT_RANKS
    if rank != "Unranked"
]

CODE_VISIBILITY_CHOICES = [
    app_commands.Choice(name="Público (código no canal)", value="public"),
    app_commands.Choice(name="Privado (código só após Entrar)", value="private"),
]

AGENT_CHOICES = [
    app_commands.Choice(name=agent, value=agent) for agent in sorted(AGENT_ROLES)
]

CLEAR_RANK_VALUE = "__clear_rank__"
CLEAR_ROLES_VALUE = "__clear_roles__"

EDIT_RANK_CHOICES = [
    app_commands.Choice(name="Sem limite (remover)", value=CLEAR_RANK_VALUE),
    *RANK_CHOICES,
]

EDIT_AGENT_CHOICES = [
    app_commands.Choice(name="Limpar roles procurados", value=CLEAR_ROLES_VALUE),
    *AGENT_CHOICES,
]

RANKS_MODE_CHOICES = [
    app_commands.Choice(name="Informativos (sem bloqueio)", value="info"),
    app_commands.Choice(name="Verificados (bloqueia ao entrar)", value="verified"),
]

class LfgCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.session_factory = session_factory
        self.event_bus = event_bus

    def _channel_allowed(self, channel_id: int) -> bool:
        allowed = self.settings.lfg_channel_id_list
        if not allowed:
            return True
        return channel_id in allowed

    def _default_mode_for_channel(self, channel: discord.abc.GuildChannel) -> str:
        name = getattr(channel, "name", "").lower()
        if "unrated" in name:
            return "Unrated"
        return self.settings.default_lfg_mode

    @app_commands.command(
        name="procurar",
        description="Criar um pedido de grupo (LFG). O modo segue o canal (ex.: unrated no nome).",
    )
    @app_commands.describe(
        vagas="Quantas pessoas precisas (1 a 4, padrão 2)",
        codigo="Código da party (opcional)",
        ranks_modo="Ranks informativos ou verificados (padrão: informativos)",
        rank_minimo="Rank mínimo (opcional)",
        rank_maximo="Rank máximo (opcional)",
        codigo_visibilidade="Quem vê o código da party no Discord",
        agente_1="Agente procurado (ex.: Initiator)",
        agente_2="Outro agente (opcional)",
    )
    @app_commands.choices(
        rank_minimo=RANK_CHOICES,
        rank_maximo=RANK_CHOICES,
        codigo_visibilidade=CODE_VISIBILITY_CHOICES,
        ranks_modo=RANKS_MODE_CHOICES,
        agente_1=AGENT_CHOICES,
        agente_2=AGENT_CHOICES,
    )
    async def procurar(
        self,
        interaction: discord.Interaction,
        vagas: app_commands.Range[int, 1, 4] = 2,
        codigo: str | None = None,
        ranks_modo: app_commands.Choice[str] | None = None,
        rank_minimo: app_commands.Choice[str] | None = None,
        rank_maximo: app_commands.Choice[str] | None = None,
        codigo_visibilidade: app_commands.Choice[str] | None = None,
        agente_1: app_commands.Choice[str] | None = None,
        agente_2: app_commands.Choice[str] | None = None,
    ) -> None:
        if interaction.channel_id is None:
            await interaction.response.send_message("Canal inválido.", ephemeral=True)
            return

        if not self._channel_allowed(interaction.channel_id):
            await interaction.response.send_message(
                "Este comando só está disponível nos canais LFG configurados.",
                ephemeral=True,
            )
            return

        if interaction.user is None or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("Comando só no servidor.", ephemeral=True)
            return

        await interaction.response.defer(thinking=False)

        party_code = codigo.strip().upper() if codigo else None
        channel = interaction.channel
        if not isinstance(channel, discord.abc.Messageable):
            await interaction.followup.send("Não foi possível publicar o pedido.", ephemeral=True)
            return

        if isinstance(channel, discord.abc.GuildChannel):
            mode = self._default_mode_for_channel(channel)
        else:
            mode = self.settings.default_lfg_mode

        visibility = codigo_visibilidade.value if codigo_visibilidade else "public"
        ranks_verified = ranks_modo is not None and ranks_modo.value == "verified"
        wanted_agents: list[str] = []
        if agente_1:
            wanted_agents.append(agente_1.value)
        if agente_2 and agente_2.value not in wanted_agents:
            wanted_agents.append(agente_2.value)

        params = LobbyCreateParams(
            mode=mode,
            slots=int(vagas),
            party_code=party_code,
            min_rank=rank_minimo.value if rank_minimo else None,
            max_rank=rank_maximo.value if rank_maximo else None,
            party_code_public=visibility == "public",
            wanted_agents=wanted_agents,
            ranks_verified=ranks_verified,
        )

        try:
            await begin_lobby_create(
                self.bot,
                channel,
                self.settings,
                self.session_factory,
                self.event_bus,
                host=interaction.user,
                params=params,
                interaction=interaction,
            )
        except Exception:
            logger.exception("procurar failed for user %s", interaction.user.id)
            await interaction.followup.send(
                "Ocorreu um erro ao criar o lobby. Tenta outra vez em instantes.",
                ephemeral=True,
            )

    @app_commands.command(
        name="perfil",
        description="Ver estatísticas LFG (nível, grupos completos, expulsões).",
    )
    @app_commands.describe(
        utilizador="Membro a consultar (opcional)",
        publico="Mostrar no canal (visível para todos)",
    )
    async def perfil(
        self,
        interaction: discord.Interaction,
        utilizador: discord.Member | None = None,
        publico: bool = False,
    ) -> None:
        if interaction.channel_id is None:
            await interaction.response.send_message("Canal inválido.", ephemeral=True)
            return

        if not self._channel_allowed(interaction.channel_id):
            await interaction.response.send_message(
                "Este comando só está disponível nos canais LFG configurados.",
                ephemeral=True,
            )
            return

        if not self.settings.gamification_enabled:
            await interaction.response.send_message(
                "A gamificação LFG não está ativa neste servidor.",
                ephemeral=True,
            )
            return

        target = utilizador or interaction.user
        if target is None:
            return

        await interaction.response.defer(ephemeral=not publico)

        async with self.session_factory() as session:
            async with session.begin():
                if isinstance(target, discord.Member):
                    await upsert_user_from_member(session, target)

        async with self.session_factory() as session:
            stats = await profile_stats(session, target.id)
            last_at = await last_completion_at(session, target.id)
            recent = await recent_completions(session, target.id, limit=3)
            rank_result = await session.execute(
                select(User.rank).where(User.discord_id == target.id)
            )
            valorant_rank = rank_result.scalar_one_or_none()

        display_name = target.display_name if hasattr(target, "display_name") else str(target)
        avatar_url = target.display_avatar.url if isinstance(target, discord.Member) else None
        built = build_profile_embed(
            stats,
            display_name=display_name,
            guild=interaction.guild,
            valorant_rank=valorant_rank,
            last_completed_at=last_at,
            recent=recent,
            avatar_url=avatar_url,
        )
        await interaction.followup.send(
            embed=built.embed,
            ephemeral=not publico,
            allowed_mentions=allowed_mentions_for_roles(built.mention_role_ids),
        )

        if isinstance(target, discord.Member) and interaction.guild is not None:
            try:
                await sync_member_lfg_roles(self.session_factory, target)
            except discord.Forbidden:
                logger.warning("sem permissão para roles LFG ao mostrar perfil de %s", target.id)
            except discord.HTTPException:
                logger.exception("falha ao sincronizar roles no /perfil")

    @app_commands.command(
        name="ranking",
        description="Top 5 da semana (funciona em qualquer canal LFG configurado).",
    )
    @app_commands.describe(publico="Mostrar no canal (visível para todos)")
    async def ranking(
        self,
        interaction: discord.Interaction,
        publico: bool = False,
    ) -> None:
        if interaction.channel_id is None:
            await interaction.response.send_message("Canal inválido.", ephemeral=True)
            return

        if not self._channel_allowed(interaction.channel_id):
            await interaction.response.send_message(
                "Este comando só está disponível nos canais LFG configurados.",
                ephemeral=True,
            )
            return

        if not self.settings.gamification_enabled:
            await interaction.response.send_message(
                "A gamificação LFG não está ativa neste servidor.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=not publico)
        embed = await weekly_leaderboard_embed(self.session_factory)
        await interaction.followup.send(embed=embed, ephemeral=not publico)

    @app_commands.command(
        name="lfg-painel",
        description="Publicar ou atualizar a mensagem fixa «Criar grupo» nos canais LFG.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        todos="Se ativo, republica em todos os canais LFG; senão só neste canal.",
    )
    async def lfg_painel(
        self,
        interaction: discord.Interaction,
        todos: bool = True,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Só no servidor.", ephemeral=True)
            return

        channel_ids = (
            self.settings.lfg_channel_id_list
            if todos
            else ([interaction.channel_id] if interaction.channel_id else [])
        )
        if not channel_ids:
            await interaction.response.send_message(
                "Não há canais LFG configurados (`LFG_CHANNEL_IDS`).",
                ephemeral=True,
            )
            return

        if not todos and interaction.channel_id is not None:
            if not self._channel_allowed(interaction.channel_id):
                await interaction.response.send_message(
                    "Este canal não está na lista LFG.",
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)
        published: list[int] = []
        failed: list[int] = []
        for channel_id in channel_ids:
            channel = interaction.guild.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                failed.append(channel_id)
                continue
            try:
                await publish_panel_message_bound(
                    self.bot,
                    channel,
                    self.settings,
                    self.session_factory,
                    self.event_bus,
                    replace_previous=True,
                )
                published.append(channel_id)
            except discord.HTTPException:
                logger.exception("lfg-painel failed for channel %s", channel_id)
                failed.append(channel_id)

        lines = [f"Painel publicado em **{len(published)}** canal(is)."]
        if failed:
            lines.append(f"Falhou em: {', '.join(str(c) for c in failed)}.")
        lines.append("Fixa a mensagem do bot no topo do canal, se quiseres.")
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(
        name="fechar",
        description="Fechar o teu pedido de grupo (LFG) ativo.",
    )
    async def fechar(self, interaction: discord.Interaction) -> None:
        if interaction.channel_id is None:
            await interaction.response.send_message("Canal inválido.", ephemeral=True)
            return

        if not self._channel_allowed(interaction.channel_id):
            await interaction.response.send_message(
                "Este comando só está disponível nos canais LFG configurados.",
                ephemeral=True,
            )
            return

        if interaction.user is None:
            return

        await interaction.response.defer(ephemeral=True)

        async with self.session_factory() as session:
            active = await lobby_service.get_host_active_lobby(session, interaction.user.id)

        if active is None:
            await interaction.followup.send("Não tens nenhum grupo aberto.", ephemeral=True)
            return

        try:
            async with self.session_factory() as session:
                async with session.begin():
                    await lobby_service.close_lobby_as_host(
                        session,
                        self.event_bus,
                        lobby_id=active.id,
                        host_id=interaction.user.id,
                    )
        except LobbyNotJoinableError as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception("fechar failed for user %s", interaction.user.id)
            await interaction.followup.send(
                "Não foi possível fechar o grupo. Tenta outra vez.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "Grupo fechado. O pedido no canal foi atualizado.",
            ephemeral=True,
        )

    @app_commands.command(
        name="editar",
        description="Editar o teu pedido LFG ativo (só alguns campos).",
    )
    @app_commands.describe(
        vagas="Novas vagas (1 a 4)",
        rank_minimo="Novo rank mínimo (ou Sem limite para remover)",
        rank_maximo="Novo rank máximo (ou Sem limite para remover)",
        codigo="Novo código da party",
        codigo_visibilidade="Público ou privado",
        ranks_modo="Ranks informativos ou verificados",
        agente_1="Roles procuradas (Initiator, etc.)",
        agente_2="Outra role procurada",
    )
    @app_commands.choices(
        rank_minimo=EDIT_RANK_CHOICES,
        rank_maximo=EDIT_RANK_CHOICES,
        codigo_visibilidade=CODE_VISIBILITY_CHOICES,
        ranks_modo=RANKS_MODE_CHOICES,
        agente_1=EDIT_AGENT_CHOICES,
        agente_2=EDIT_AGENT_CHOICES,
    )
    async def editar(
        self,
        interaction: discord.Interaction,
        vagas: app_commands.Range[int, 1, 4] | None = None,
        ranks_modo: app_commands.Choice[str] | None = None,
        rank_minimo: app_commands.Choice[str] | None = None,
        rank_maximo: app_commands.Choice[str] | None = None,
        codigo: str | None = None,
        codigo_visibilidade: app_commands.Choice[str] | None = None,
        agente_1: app_commands.Choice[str] | None = None,
        agente_2: app_commands.Choice[str] | None = None,
    ) -> None:
        if interaction.channel_id is None:
            await interaction.response.send_message("Canal inválido.", ephemeral=True)
            return

        if not self._channel_allowed(interaction.channel_id):
            await interaction.response.send_message(
                "Este comando só está disponível nos canais LFG configurados.",
                ephemeral=True,
            )
            return

        if interaction.user is None:
            return

        patch = LobbyHostPatch()
        if vagas is not None:
            patch.slots = int(vagas)
        if rank_minimo is not None:
            patch.min_rank = (
                None if rank_minimo.value == CLEAR_RANK_VALUE else rank_minimo.value
            )
        if rank_maximo is not None:
            patch.max_rank = (
                None if rank_maximo.value == CLEAR_RANK_VALUE else rank_maximo.value
            )
        if codigo is not None:
            stripped = codigo.strip()
            patch.party_code = stripped.upper() if stripped else None
        if codigo_visibilidade is not None:
            patch.party_code_public = codigo_visibilidade.value == "public"
        if ranks_modo is not None:
            patch.ranks_verified = ranks_modo.value == "verified"
        if agente_1 is not None or agente_2 is not None:
            if agente_1 is not None and agente_1.value == CLEAR_ROLES_VALUE:
                patch.wanted_agents = []
            else:
                wanted: list[str] = []
                if agente_1 is not None and agente_1.value != CLEAR_ROLES_VALUE:
                    wanted.append(agente_1.value)
                if agente_2 is not None and agente_2.value != CLEAR_ROLES_VALUE:
                    if agente_2.value not in wanted:
                        wanted.append(agente_2.value)
                patch.wanted_agents = wanted

        if patch.is_empty():
            await interaction.response.send_message(
                "Indica pelo menos um campo para alterar (vagas, ranks, código, etc.).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        async with self.session_factory() as session:
            active = await lobby_service.get_host_active_lobby(session, interaction.user.id)

        if active is None:
            await interaction.followup.send("Não tens nenhum grupo aberto para editar.", ephemeral=True)
            return

        try:
            async with self.session_factory() as session:
                async with session.begin():
                    await lobby_service.update_lobby_as_host(
                        session,
                        self.event_bus,
                        lobby_id=active.id,
                        host_id=interaction.user.id,
                        patch=patch,
                    )
        except (LobbyEditError, LobbyNotJoinableError, RankRangeError) as exc:
            await interaction.followup.send(str(exc), ephemeral=True)
            return
        except Exception:
            logger.exception("editar failed for user %s", interaction.user.id)
            await interaction.followup.send(
                "Não foi possível editar o pedido. Tenta outra vez.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            "Pedido atualizado. A mensagem no canal foi refrescada.",
            ephemeral=True,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is not None and isinstance(message.channel, discord.TextChannel):
            if self._channel_allowed(message.channel.id):
                await notify_panel_sticky_activity(
                    self.bot,
                    self.settings,
                    self.session_factory,
                    self.event_bus,
                    message,
                )

        if not self.settings.auto_format_messages:
            return
        if message.author.bot or message.guild is None:
            return
        if not self._channel_allowed(message.channel.id):
            return
        if not isinstance(message.author, discord.Member):
            return

        parsed = parse_lfg_message(message.content)
        if parsed is None:
            return

        min_rank, max_rank = parsed.min_rank, parsed.max_rank
        wanted_agents: list[str] = []
        if message.role_mentions:
            from_roles_min, from_roles_max = extract_rank_bounds_from_roles(message.role_mentions)
            if from_roles_min:
                min_rank = from_roles_min
            if from_roles_max:
                max_rank = from_roles_max
            wanted_agents = extract_wanted_agents_from_roles(message.role_mentions)

        mode = self._default_mode_for_channel(message.channel)
        params = LobbyCreateParams(
            mode=mode,
            slots=parsed.slots,
            party_code=parsed.party_code,
            min_rank=min_rank,
            max_rank=max_rank,
            wanted_agents=wanted_agents,
        )
        try:
            outcome = await begin_lobby_create(
                self.bot,
                message.channel,
                self.settings,
                self.session_factory,
                self.event_bus,
                host=message.author,
                params=params,
                reference=message,
            )
            if outcome == "published":
                try:
                    await message.add_reaction("✅")
                except discord.HTTPException:
                    pass
        except Exception:
            logger.exception("auto-format failed for message %s", message.id)


async def setup_lfg_cog(
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
) -> None:
    await bot.add_cog(LfgCog(bot, settings, session_factory, event_bus))
