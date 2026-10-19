from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.bot.discord_roles import extract_rank_bounds_from_roles, extract_wanted_agents_from_roles
from app.bot.embeds import allowed_mentions_for_roles
from app.bot.gamification_roles import sync_member_lfg_roles
from app.bot.reputation_roles import sync_member_reputation_roles
from app.bot.ranking_embed import (
    RANKING_PAGE_SIZE,
    all_time_creators_embed_paged,
    reputation_leaderboard_embed,
)
from app.bot.guild_audit_log import send_guild_audit_log
from app.bot.host_cooldown import resolve_host_recreate_cooldown
from app.bot.lfg_panel import notify_panel_sticky_activity, publish_panel_message_bound
from app.bot.message_context_menus import register_message_context_menus
from app.bot.lobby_create import LobbyCreateParams, begin_lobby_create
from app.bot.members import upsert_user_from_member
from app.bot.message_parser import parse_lfg_message
from app.bot.party_code_config import party_code_max_length_from_runtime
from app.bot.profile_embed import build_profile_embed
from app.core.config import Settings
from app.core.events import EventBus
from app.db.models import User
from app.services import lobbies as lobby_service
from app.services.errors import (
    LobbyEditError,
    LobbyNotJoinableError,
    PartyCodeInUseError,
    PartyCodeInvalidError,
    RankRangeError,
)
from app.services.gamification import last_completion_at, profile_stats, recent_completions
from app.services.guild_config import GuildConfigService, GuildRuntimeConfig
from app.db.models import GuildSettings
from app.services.guild_stats import guild_lobby_stats, guild_lobby_stats_lifetime
from app.services.lobby_patch import LobbyHostPatch
from app.services.lobby_post_style import (
    POST_STYLE_INTERACTIVE,
    POST_STYLE_SIMPLE,
    is_simple_post_style,
    normalize_post_style,
    resolve_post_style_for_guild,
)
from app.services.lobby_source import LOBBY_SOURCE_CHAT, LOBBY_SOURCE_SLASH
from app.services.ranks import AGENT_ROLES, VALORANT_RANKS
from app.services.user_privacy import delete_user_personal_data, user_exists

logger = logging.getLogger(__name__)

RANK_CHOICES = [
    app_commands.Choice(
        name="Unranked (sem ranked)" if rank == "Unranked" else rank,
        value=rank,
    )
    for rank in VALORANT_RANKS
]

CODE_VISIBILITY_CHOICES = [
    app_commands.Choice(name="Público (código no canal)", value="public"),
    app_commands.Choice(name="Privado (código só após Entrar)", value="private"),
]

AGENT_CHOICES = [app_commands.Choice(name=agent, value=agent) for agent in sorted(AGENT_ROLES)]

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

POST_STYLE_CHOICES = [
    app_commands.Choice(
        name="Simples (código no canal, fecha com /fechar)",
        value=POST_STYLE_SIMPLE,
    ),
    app_commands.Choice(
        name="Detalhado (Entrar/Sair e opções)",
        value=POST_STYLE_INTERACTIVE,
    ),
]


class LfgCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        guild_config: GuildConfigService,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.session_factory = session_factory
        self.event_bus = event_bus
        self.guild_config = guild_config

    async def _channel_allowed(self, guild_id: int | None, channel_id: int) -> bool:
        return await self.guild_config.channel_allowed(self.session_factory, guild_id, channel_id)

    async def _guild_runtime(self, guild_id: int) -> GuildRuntimeConfig:
        return await self.guild_config.get_config_for_factory(self.session_factory, guild_id)

    def _default_mode_for_channel(
        self, channel: discord.abc.GuildChannel, runtime: GuildRuntimeConfig | None = None
    ) -> str:
        name = getattr(channel, "name", "").lower()
        if "unrated" in name:
            return "Unrated"
        if runtime is not None:
            return runtime.default_lfg_mode
        return self.settings.default_lfg_mode

    @app_commands.command(
        name="procurar",
        description="Publicar pedido simples (código + vagas). Modo do canal segue o nome (ex.: unrated).",
    )
    @app_commands.describe(
        vagas="Quantas pessoas precisas (1 a 4, padrão 2)",
        codigo="Código da party (tamanho definido no /admin; recomendado no simples)",
        tipo="Opcional: Detalhado = Entrar/Sair e mais opções no Discord",
        rank_minimo="Rank mínimo (opcional)",
        rank_maximo="Rank máximo (opcional)",
        ranks_modo="(só detalhado) Ranks informativos ou verificados",
        codigo_visibilidade="(só detalhado) Código público ou privado no Discord",
        agente_1="(só detalhado) Agente procurado",
        agente_2="(só detalhado) Outro agente",
    )
    @app_commands.choices(
        tipo=POST_STYLE_CHOICES,
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
        tipo: app_commands.Choice[str] | None = None,
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

        guild_id = interaction.guild.id if interaction.guild else None
        if not await self._channel_allowed(guild_id, interaction.channel_id):
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

        runtime = await self._guild_runtime(guild_id) if guild_id is not None else None
        if isinstance(channel, discord.abc.GuildChannel):
            mode = self._default_mode_for_channel(channel, runtime)
        else:
            mode = runtime.default_lfg_mode if runtime else self.settings.default_lfg_mode

        post_style = resolve_post_style_for_guild(
            tipo.value if tipo else None,
            simple_enabled=runtime.lfg_post_style_simple_enabled if runtime else True,
            detailed_enabled=runtime.lfg_post_style_detailed_enabled if runtime else True,
        )
        simple = is_simple_post_style(post_style)
        if simple:
            visibility = "public"
            ranks_verified = False
            wanted_agents: list[str] = []
        else:
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
            post_style=post_style,
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
                guild_config=self.guild_config,
                create_source=LOBBY_SOURCE_SLASH,
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
        if interaction.guild is None:
            await interaction.response.send_message(
                "Este comando só funciona num servidor.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id
        runtime = await self._guild_runtime(guild_id) if guild_id is not None else None
        gamification_on = (
            runtime.gamification_enabled if runtime else self.settings.gamification_enabled
        )

        target = utilizador or interaction.user
        if target is None:
            return

        await interaction.response.defer(ephemeral=not publico)

        async with self.session_factory() as session:
            async with session.begin():
                if isinstance(target, discord.Member):
                    await upsert_user_from_member(session, target)

        async with self.session_factory() as session:
            stats = await profile_stats(
                session,
                target.id,
                discord_guild_id=guild_id,
            )
            last_at = await last_completion_at(session, target.id)
            recent = await recent_completions(session, target.id, limit=3)
            rank_result = await session.execute(
                select(User.rank).where(User.discord_id == target.id)
            )
            valorant_rank = rank_result.scalar_one_or_none()
            from app.services.reputation import user_reputation_score

            reputation_score = await user_reputation_score(
                session, discord_guild_id=guild_id, user_id=target.id
            )

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
            reputation_score=reputation_score,
        )
        await interaction.followup.send(
            embed=built.embed,
            ephemeral=not publico,
            allowed_mentions=allowed_mentions_for_roles(built.mention_role_ids),
        )

        if isinstance(target, discord.Member):
            try:
                await sync_member_reputation_roles(
                    self.session_factory, self.guild_config, target
                )
            except discord.Forbidden:
                logger.warning(
                    "sem permissão para roles de reputação ao mostrar perfil de %s",
                    target.id,
                )
            except discord.HTTPException:
                logger.exception("falha ao sincronizar roles de reputação no /perfil")

        if (
            gamification_on
            and isinstance(target, discord.Member)
            and interaction.guild is not None
        ):
            try:
                await sync_member_lfg_roles(self.session_factory, target)
            except discord.Forbidden:
                logger.warning("sem permissão para roles LFG ao mostrar perfil de %s", target.id)
            except discord.HTTPException:
                logger.exception("falha ao sincronizar roles no /perfil")

    @app_commands.command(
        name="ranking",
        description="Ranking de grupos LFG criados (histórico completo, com páginas).",
    )
    @app_commands.describe(
        pagina="Página do ranking (10 pessoas por página)",
        publico="Mostrar no canal (visível para todos)",
    )
    async def ranking(
        self,
        interaction: discord.Interaction,
        pagina: app_commands.Range[int, 1, 100] = 1,
        publico: bool = False,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Este comando só funciona num servidor.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id
        await interaction.response.defer(ephemeral=not publico)
        embed = await all_time_creators_embed_paged(
            self.session_factory,
            discord_guild_id=guild_id,
            page=pagina,
            page_size=RANKING_PAGE_SIZE,
        )
        await interaction.followup.send(embed=embed, ephemeral=not publico)

    @app_commands.command(
        name="reputacao",
        description="Ranking de reputação LFG (votos após grupos completos).",
    )
    @app_commands.describe(
        pagina="Página do ranking (10 pessoas por página)",
        publico="Mostrar no canal (visível para todos)",
    )
    async def reputacao(
        self,
        interaction: discord.Interaction,
        pagina: app_commands.Range[int, 1, 100] = 1,
        publico: bool = False,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message(
                "Este comando só funciona num servidor.",
                ephemeral=True,
            )
            return

        guild_id = interaction.guild.id
        runtime = await self._guild_runtime(guild_id)
        reputation_on = bool(runtime and int(runtime.reputation_channel_id or 0) > 0)
        if not reputation_on:
            await interaction.response.send_message(
                "A reputação LFG ainda não está configurada neste servidor "
                "(canal no dashboard → Geral).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=not publico)
        embed = await reputation_leaderboard_embed(
            self.session_factory,
            discord_guild_id=guild_id,
            page=pagina,
            page_size=RANKING_PAGE_SIZE,
        )
        await interaction.followup.send(embed=embed, ephemeral=not publico)

    @app_commands.command(
        name="reputacao-ajustar",
        description="(Staff) Adicionar ou remover pontos de reputação LFG a um membro.",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(
        utilizador="Membro a ajustar",
        pontos="Pontos a somar (negativo para remover, ex.: -5 ou 10)",
        motivo="Motivo opcional (aparece no log do servidor)",
    )
    async def reputacao_ajustar(
        self,
        interaction: discord.Interaction,
        utilizador: discord.Member,
        pontos: int,
        motivo: str | None = None,
    ) -> None:
        if interaction.guild is None or interaction.user is None:
            await interaction.response.send_message("Servidor inválido.", ephemeral=True)
            return

        from app.services.reputation import (
            add_reputation_adjustment,
            clamp_reputation_adjust_delta,
        )

        delta = clamp_reputation_adjust_delta(pontos)
        if delta == 0:
            await interaction.response.send_message(
                "Indica pontos diferentes de zero (entre -500 e 500).",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = interaction.guild.id
        async with self.session_factory() as session:
            async with session.begin():
                await upsert_user_from_member(session, utilizador)
                if isinstance(interaction.user, discord.Member):
                    await upsert_user_from_member(session, interaction.user)
                new_score = await add_reputation_adjustment(
                    session,
                    discord_guild_id=guild_id,
                    user_id=utilizador.id,
                    delta=delta,
                    created_by_id=interaction.user.id,
                )

        try:
            await sync_member_reputation_roles(
                self.session_factory, self.guild_config, utilizador
            )
        except discord.HTTPException:
            logger.exception("falha ao sincronizar roles após ajuste de reputação")

        sign = "+" if delta > 0 else ""
        reason_line = f"\nMotivo: {motivo.strip()}" if motivo and motivo.strip() else ""
        await interaction.followup.send(
            f"Ajustei a reputação de {utilizador.mention}: **{sign}{delta}** "
            f"(total **{new_score}**).{reason_line}",
            ephemeral=True,
        )

        from app.bot.guild_audit_log import send_guild_audit_log

        await send_guild_audit_log(
            self.bot,
            self.guild_config,
            self.session_factory,
            guild_id,
            title="Reputação · ajuste manual",
            description=(
                f"<@{interaction.user.id}> aplicou **{sign}{delta}** a <@{utilizador.id}> "
                f"(total **{new_score}**).{reason_line}"
            ),
            colour=discord.Colour.blurple(),
        )

    @app_commands.command(
        name="lfg-stats",
        description="Métricas LFG do servidor (staff).",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(dias="Janela em dias (1–90).")
    async def lfg_stats(
        self,
        interaction: discord.Interaction,
        dias: app_commands.Range[int, 1, 90] = 30,
    ) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Só no servidor.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        runtime = await self._guild_runtime(interaction.guild.id)
        channel_ids = list(runtime.lfg_channel_ids) if runtime else []
        async with self.session_factory() as session:
            legacy_row = await session.get(GuildSettings, interaction.guild.id)
            legacy_lobbies = int(legacy_row.stats_legacy_lobbies_created or 0) if legacy_row else 0
            legacy_joins = int(legacy_row.stats_legacy_joins or 0) if legacy_row else 0
            legacy_users = int(legacy_row.stats_legacy_users or 0) if legacy_row else 0
            stats = await guild_lobby_stats(
                session,
                discord_guild_id=interaction.guild.id,
                channel_ids=channel_ids,
                days=int(dias),
            )
            lifetime = await guild_lobby_stats_lifetime(
                session,
                discord_guild_id=interaction.guild.id,
                channel_ids=channel_ids,
                legacy_lobbies=legacy_lobbies,
                legacy_joins=legacy_joins,
                legacy_users=legacy_users,
            )

        by_source = stats["created_by_source"]
        lines = [
            f"**Métricas LFG** (últimos **{dias}** dias)",
            f"• Pedidos criados: **{stats['lobbies_created_period']}**",
            f"  └ `/procurar`: {by_source['slash']} · painel: {by_source['panel']} · "
            f"chat: {by_source['chat']} · outro: {by_source['unknown']}",
            f"• **Desde sempre** (bot + histórico): pedidos **{lifetime['lobbies_created_lifetime']}** · "
            f"entradas **{lifetime['joins_lifetime']}** · utilizadores **{lifetime['users_lifetime']}**",
            f"• Ativos agora: **{stats['active_lobbies']}**",
            f"• Entradas em lobbies: **{stats['joins_period']}**",
            f"• Grupos cheios (filled): **{stats['groups_filled_period']}**",
            f"• Grupos completos (gamificação): **{stats['groups_completed_period']}**",
            f"• Utilizadores distintos (7d): **{stats['active_users_7d']}**",
            f"• Tempo médio até cheio: **{stats['avg_minutes_to_fill']}** min",
            f"• Tempo médio até fechar/expirar: **{stats['avg_minutes_to_end']}** min",
        ]
        await interaction.followup.send("\n".join(lines), ephemeral=True)

    @app_commands.command(
        name="lfg-guia",
        description="Publicar ou atualizar o guia de uso do LFG no canal configurado.",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def lfg_guia(self, interaction: discord.Interaction) -> None:
        if interaction.guild is None:
            await interaction.response.send_message("Só no servidor.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        from app.bot.guide_channel import publish_guild_guide

        ok = await publish_guild_guide(self.bot, self.session_factory, interaction.guild.id)
        if not ok:
            await interaction.followup.send(
                "Define primeiro o **canal do guia** no dashboard /admin e guarda.",
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            "Guia publicado ou atualizado no canal configurado. Fixa a mensagem no topo, se quiseres.",
            ephemeral=True,
        )

    @app_commands.command(
        name="lfg-apagar-dados",
        description="Pedir remoção dos teus dados LFG guardados pelo bot (RGPD).",
    )
    @app_commands.describe(
        utilizador="Staff: apagar dados de outro membro (requer Gerir servidor).",
    )
    async def lfg_apagar_dados(
        self,
        interaction: discord.Interaction,
        utilizador: discord.Member | None = None,
    ) -> None:
        if interaction.user is None:
            return
        target = utilizador or interaction.user
        if utilizador is not None and utilizador.id != interaction.user.id:
            perms = (
                interaction.user.guild_permissions
                if isinstance(interaction.user, discord.Member)
                else None
            )
            if perms is None or not perms.manage_guild:
                await interaction.response.send_message(
                    "Só staff com **Gerir servidor** pode apagar dados de outro membro.",
                    ephemeral=True,
                )
                return

        await interaction.response.defer(ephemeral=True)
        async with self.session_factory() as session:
            if not await user_exists(session, target.id):
                await interaction.followup.send(
                    "Não há dados guardados para esse utilizador.",
                    ephemeral=True,
                )
                return
        async with self.session_factory() as session:
            async with session.begin():
                result = await delete_user_personal_data(session, target.id)

        if not result.user_anonymized:
            await interaction.followup.send(
                "Não há dados guardados para esse utilizador.",
                ephemeral=True,
            )
            return

        if target.id == interaction.user.id:
            msg = (
                "Os teus dados pessoais LFG foram anonimizados: nome e rank removidos, "
                "histórico de entradas e pontos de gamificação apagados. "
                "Pedidos antigos em que eras host mantêm-se no canal, com nome genérico."
            )
        else:
            msg = (
                f"Dados LFG de {target.mention} anonimizados "
                f"({result.memberships_removed} entradas, "
                f"{result.completions_removed} registos de gamificação)."
            )
        await interaction.followup.send(msg, ephemeral=True)

        if interaction.guild is not None:
            actor = interaction.user.mention
            await send_guild_audit_log(
                self.bot,
                self.guild_config,
                self.session_factory,
                interaction.guild.id,
                title="RGPD — dados LFG apagados",
                description=(
                    f"**Alvo:** {target.mention} (`{target.id}`)\n"
                    f"**Pedido por:** {actor}\n"
                    f"**Entradas removidas:** {result.memberships_removed}\n"
                    f"**Gamificação removida:** {result.completions_removed}"
                ),
                colour=discord.Colour.purple(),
            )

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

        runtime = await self._guild_runtime(interaction.guild.id)
        channel_ids = (
            list(runtime.lfg_channel_ids)
            if todos
            else ([interaction.channel_id] if interaction.channel_id else [])
        )
        if not channel_ids:
            await interaction.response.send_message(
                "Não há canais LFG configurados para este servidor.",
                ephemeral=True,
            )
            return

        if not todos and interaction.channel_id is not None:
            if not await self._channel_allowed(interaction.guild.id, interaction.channel_id):
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
                    self.guild_config,
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

        guild_id = interaction.guild.id if interaction.guild else None
        if not await self._channel_allowed(guild_id, interaction.channel_id):
            await interaction.response.send_message(
                "Este comando só está disponível nos canais LFG configurados.",
                ephemeral=True,
            )
            return

        if interaction.user is None:
            return

        await interaction.response.defer(ephemeral=True)

        async with self.session_factory() as session:
            active = await lobby_service.get_host_active_lobby(
                session, interaction.user.id, include_past_ttl=True
            )

        if active is None:
            await interaction.followup.send("Não tens nenhum grupo aberto.", ephemeral=True)
            return

        channel = interaction.channel
        host = interaction.user
        if channel is None or not isinstance(host, discord.Member):
            await interaction.followup.send("Canal inválido.", ephemeral=True)
            return

        host_recreate_cooldown = await resolve_host_recreate_cooldown(
            self.guild_config,
            self.session_factory,
            host,
            channel,
        )

        try:
            async with self.session_factory() as session:
                async with session.begin():
                    await lobby_service.close_lobby_as_host(
                        session,
                        self.event_bus,
                        lobby_id=active.id,
                        host_id=interaction.user.id,
                        host_recreate_cooldown=host_recreate_cooldown,
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
        codigo="Novo código da party (tamanho definido no /admin)",
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

        guild_id = interaction.guild.id if interaction.guild else None
        if not await self._channel_allowed(guild_id, interaction.channel_id):
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
            patch.min_rank = None if rank_minimo.value == CLEAR_RANK_VALUE else rank_minimo.value
        if rank_maximo is not None:
            patch.max_rank = None if rank_maximo.value == CLEAR_RANK_VALUE else rank_maximo.value
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
            await interaction.followup.send(
                "Não tens nenhum grupo aberto para editar.", ephemeral=True
            )
            return

        runtime = await self._guild_runtime(guild_id) if guild_id is not None else None
        code_len = party_code_max_length_from_runtime(runtime)
        try:
            async with self.session_factory() as session:
                async with session.begin():
                    await lobby_service.update_lobby_as_host(
                        session,
                        self.event_bus,
                        lobby_id=active.id,
                        host_id=interaction.user.id,
                        patch=patch,
                        party_code_max_length=code_len,
                    )
        except (
            LobbyEditError,
            LobbyNotJoinableError,
            RankRangeError,
            PartyCodeInUseError,
            PartyCodeInvalidError,
        ) as exc:
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
            if await self._channel_allowed(message.guild.id, message.channel.id):
                await notify_panel_sticky_activity(
                    self.bot,
                    self.settings,
                    self.session_factory,
                    self.event_bus,
                    message,
                    self.guild_config,
                )

        runtime = await self._guild_runtime(message.guild.id) if message.guild is not None else None
        auto_format = (
            runtime.auto_format_messages if runtime else self.settings.auto_format_messages
        )
        if not auto_format:
            return
        if message.author.bot or message.guild is None:
            return
        if not await self._channel_allowed(message.guild.id, message.channel.id):
            return
        if not isinstance(message.author, discord.Member):
            return

        code_len = party_code_max_length_from_runtime(runtime)
        parsed = parse_lfg_message(
            message.content, party_code_max_length=code_len
        )
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

        mode = self._default_mode_for_channel(message.channel, runtime)
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
                guild_config=self.guild_config,
                create_source=LOBBY_SOURCE_CHAT,
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
    guild_config: GuildConfigService,
) -> None:
    await bot.add_cog(LfgCog(bot, settings, session_factory, event_bus, guild_config))
    register_message_context_menus(bot)
