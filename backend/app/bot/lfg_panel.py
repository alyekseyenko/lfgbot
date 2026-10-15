from __future__ import annotations

import asyncio
import logging
import re
import time

import discord
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.events import EventBus
from app.db.models import LfgPanelPost
from app.services.errors import RankRangeError
from app.services.guild_config import GuildConfigService
from app.services.lfg_embed_style import (
    DEFAULT_COMPETITIVE_COLOR,
    DEFAULT_PANEL_CTA,
    DEFAULT_PANEL_LEAD,
    LobbyEmbedStyle,
    embed_custom_text,
    lobby_embed_style_from_config,
    parse_embed_hex_color,
)
from app.services.lobby_source import LOBBY_SOURCE_PANEL
from app.services.ranks import VALORANT_RANKS, normalize_rank_name, validate_rank_range

RANK_SELECT_NONE = "__none__"

logger = logging.getLogger(__name__)

PANEL_BUTTON_CUSTOM_ID = "lfg:panel:create"
PANEL_EMBED_TITLE = "LFG — Criar grupo"
PANEL_EMBED_DESCRIPTION = (
    "Clica em **Criar grupo**.\n\n"
    "**1.** Vagas e código da party (o essencial)\n"
    "**2.** Ranks opcionais em dropdown (mín. / máx., como as roles)\n"
    "**3.** **Publicar** — o pedido fica neste canal com Entrar / Sair\n\n"
    "O formulário é só para ti; o grupo é público.\n"
    "Ainda podes escrever no chat (`ABC123 +2`) ou usar `/procurar` para mais opções."
)

_SLOTS_RE = re.compile(r"^[1-4]$")


def channel_allowed(settings: Settings, channel_id: int) -> bool:
    allowed = settings.lfg_channel_id_list
    if not allowed:
        return True
    return channel_id in allowed


async def channel_allowed_async(
    guild_config: GuildConfigService,
    session_factory: async_sessionmaker[AsyncSession],
    guild_id: int | None,
    channel_id: int,
) -> bool:
    return await guild_config.channel_allowed(session_factory, guild_id, channel_id)


async def collect_lfg_channel_ids(
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
) -> list[int]:
    channel_ids: set[int] = set()
    async with session_factory() as session:
        for guild_id in await guild_config.list_installed_guild_ids(session):
            cfg = await guild_config.get_config(session, guild_id)
            channel_ids.update(cfg.lfg_channel_ids)
    if not channel_ids:
        channel_ids.update(settings.lfg_channel_id_list)
    return sorted(channel_ids)


def default_mode_for_channel(settings: Settings, channel: discord.abc.GuildChannel) -> str:
    name = getattr(channel, "name", "").lower()
    if "unrated" in name:
        return "Unrated"
    return settings.default_lfg_mode


def parse_panel_slots(raw: str) -> int | None:
    text = raw.strip()
    if not _SLOTS_RE.match(text):
        return None
    return int(text)


def parse_optional_panel_rank(raw: str) -> str | None:
    text = raw.strip()
    if not text:
        return None
    return normalize_rank_name(text)


def rank_select_options() -> list[discord.SelectOption]:
    options = [
        discord.SelectOption(label="Sem limite", value=RANK_SELECT_NONE, emoji="♾️"),
    ]
    for rank in VALORANT_RANKS:
        label = "Unranked (sem ranked)" if rank == "Unranked" else rank
        options.append(discord.SelectOption(label=label, value=rank))
    return options


def rank_from_select_value(value: str) -> str | None:
    if value == RANK_SELECT_NONE:
        return None
    return value


async def execute_panel_lobby_create(
    interaction: discord.Interaction,
    panel: CreateGroupPanelView,
    *,
    slots: int,
    party_code: str | None,
    min_rank: str | None,
    max_rank: str | None,
) -> None:
    if panel.bot is None or panel.settings is None or panel.session_factory is None:
        await interaction.followup.send("Bot em arranque. Tenta outra vez.", ephemeral=True)
        return
    if interaction.user is None or not isinstance(interaction.user, discord.Member):
        await interaction.followup.send("Só no servidor.", ephemeral=True)
        return
    channel = interaction.channel
    if channel is None or not isinstance(channel, discord.abc.Messageable):
        await interaction.followup.send("Canal inválido.", ephemeral=True)
        return

    try:
        validate_rank_range(min_rank, max_rank)
    except RankRangeError as exc:
        await interaction.followup.send(str(exc), ephemeral=True)
        return

    runtime = None
    if panel.guild_config is not None and interaction.guild is not None:
        runtime = await panel.guild_config.get_config_for_factory(
            panel.session_factory, interaction.guild.id
        )
    if isinstance(channel, discord.abc.GuildChannel):
        name = getattr(channel, "name", "").lower()
        if "unrated" in name:
            mode = "Unrated"
        elif runtime is not None:
            mode = runtime.default_lfg_mode
        else:
            mode = default_mode_for_channel(panel.settings, channel)
    else:
        mode = runtime.default_lfg_mode if runtime else panel.settings.default_lfg_mode

    from app.bot.lobby_create import LobbyCreateParams, begin_lobby_create

    params = LobbyCreateParams(
        mode=mode,
        slots=slots,
        party_code=party_code,
        min_rank=min_rank,
        max_rank=max_rank,
        party_code_public=True,
        wanted_agents=[],
        ranks_verified=False,
    )
    try:
        await begin_lobby_create(
            panel.bot,
            channel,
            panel.settings,
            panel.session_factory,
            panel.event_bus,
            host=interaction.user,
            params=params,
            interaction=interaction,
            guild_config=panel.guild_config,
            create_source=LOBBY_SOURCE_PANEL,
        )
    except Exception:
        logger.exception("panel create failed for user %s", interaction.user.id)
        await interaction.followup.send(
            "Não foi possível publicar o pedido. Tenta outra vez.",
            ephemeral=True,
        )


def _panel_title(decorative: bool) -> str:
    if decorative:
        return f"🎯 {PANEL_EMBED_TITLE}"
    return PANEL_EMBED_TITLE


def _message_has_panel_button(message: discord.Message) -> bool:
    for row in getattr(message, "components", ()) or ():
        for child in row.children:
            if getattr(child, "custom_id", None) == PANEL_BUTTON_CUSTOM_ID:
                return True
    return False


def is_panel_message(message: discord.Message, bot_user_id: int | None) -> bool:
    if bot_user_id is None or message.author.id != bot_user_id:
        return False
    if _message_has_panel_button(message):
        return True
    if not message.embeds:
        return False
    title = message.embeds[0].title or ""
    return PANEL_EMBED_TITLE in title


def build_panel_embed(embed_style: LobbyEmbedStyle | None = None) -> discord.Embed:
    decorative = embed_style.panel_decorative if embed_style is not None else True
    custom_title = embed_custom_text(embed_style, "panel_title", "")
    title = custom_title if custom_title else _panel_title(decorative)
    custom_body = embed_custom_text(embed_style, "panel_description", "")
    if custom_body:
        description = custom_body
    else:
        description = PANEL_EMBED_DESCRIPTION
        if decorative:
            lead = embed_custom_text(embed_style, "panel_lead", DEFAULT_PANEL_LEAD)
            cta = embed_custom_text(embed_style, "panel_cta", DEFAULT_PANEL_CTA)
            description = f"{lead}\n\n{PANEL_EMBED_DESCRIPTION}\n\n{cta}"
    hex_color = (
        parse_embed_hex_color(embed_style.panel_color, default=DEFAULT_COMPETITIVE_COLOR)
        if embed_style is not None
        else DEFAULT_COMPETITIVE_COLOR
    )
    embed = discord.Embed(
        title=title,
        description=description,
        color=int(hex_color, 16),
    )
    if embed_style is not None:
        brand = (embed_style.panel_footer_brand or embed_style.footer_brand or "").strip()
        if brand:
            embed.set_footer(text=brand)
        if embed_style.panel_thumbnail_url:
            embed.set_thumbnail(url=embed_style.panel_thumbnail_url)
        panel_banner = (embed_style.panel_banner_url or "").strip()
        if not panel_banner and embed_style.banner_on_panel:
            panel_banner = (embed_style.banner_url or "").strip()
        if panel_banner:
            embed.set_image(url=panel_banner)
    return embed


async def _panel_embed_for_guild(
    session_factory: async_sessionmaker[AsyncSession],
    guild_config: GuildConfigService,
    guild_id: int | None,
) -> discord.Embed:
    if guild_id is None:
        return build_panel_embed()
    cfg = await guild_config.get_config_for_factory(session_factory, guild_id)
    if cfg is None:
        return build_panel_embed()
    return build_panel_embed(lobby_embed_style_from_config(cfg))


def rank_extras_prompt(*, slots: int, party_code: str | None) -> str:
    code_line = f"`{party_code}`" if party_code else "sem código"
    return (
        f"Pedido: **{slots}** vaga(s), código {code_line}.\n"
        "Opcional: escolhe **rank mínimo** e **máximo** nos menus "
        "(como as roles). Depois clica **Publicar**.\n"
        "Se não escolheres nada, o pedido fica para qualquer rank."
    )


class PanelRankExtrasView(discord.ui.View):
    def __init__(
        self,
        panel: CreateGroupPanelView,
        *,
        slots: int,
        party_code: str | None,
        user_id: int,
    ) -> None:
        super().__init__(timeout=180)
        self._panel = panel
        self._slots = slots
        self._party_code = party_code
        self._user_id = user_id
        self._min_rank: str | None = None
        self._max_rank: str | None = None

        self._min_select: discord.ui.Select[PanelRankExtrasView] = discord.ui.Select(
            placeholder="Rank mínimo (opcional)",
            options=rank_select_options(),
            min_values=1,
            max_values=1,
        )
        self._min_select.callback = self._on_min_rank
        self.add_item(self._min_select)

        self._max_select: discord.ui.Select[PanelRankExtrasView] = discord.ui.Select(
            placeholder="Rank máximo (opcional)",
            options=rank_select_options(),
            min_values=1,
            max_values=1,
        )
        self._max_select.callback = self._on_max_rank
        self.add_item(self._max_select)

        publish_btn: discord.ui.Button[PanelRankExtrasView] = discord.ui.Button(
            label="Publicar",
            style=discord.ButtonStyle.success,
        )
        publish_btn.callback = self._on_publish
        self.add_item(publish_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user is None or interaction.user.id != self._user_id:
            await interaction.response.send_message(
                "Só quem criou o pedido pode continuar.",
                ephemeral=True,
            )
            return False
        return True

    async def _on_min_rank(self, interaction: discord.Interaction) -> None:
        chosen = self._min_select.values[0] if self._min_select.values else RANK_SELECT_NONE
        self._min_rank = rank_from_select_value(chosen)
        await interaction.response.defer()

    async def _on_max_rank(self, interaction: discord.Interaction) -> None:
        chosen = self._max_select.values[0] if self._max_select.values else RANK_SELECT_NONE
        self._max_rank = rank_from_select_value(chosen)
        await interaction.response.defer()

    def _disable_all(self) -> None:
        for item in self.children:
            if isinstance(item, (discord.ui.Button, discord.ui.Select)):
                item.disabled = True

    async def _on_publish(self, interaction: discord.Interaction) -> None:
        try:
            validate_rank_range(self._min_rank, self._max_rank)
        except RankRangeError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return

        self._disable_all()
        await interaction.response.edit_message(view=self)
        await execute_panel_lobby_create(
            interaction,
            self._panel,
            slots=self._slots,
            party_code=self._party_code,
            min_rank=self._min_rank,
            max_rank=self._max_rank,
        )


class CreateGroupModal(discord.ui.Modal, title="Criar pedido LFG"):
    vagas = discord.ui.TextInput(
        label="Quantas vagas? (1 a 4)",
        placeholder="2",
        default="2",
        min_length=1,
        max_length=1,
        required=True,
    )
    codigo = discord.ui.TextInput(
        label="Código da party (opcional)",
        placeholder="ABC123",
        required=False,
        max_length=32,
    )

    def __init__(self, panel: CreateGroupPanelView) -> None:
        super().__init__()
        self._panel = panel

    async def on_submit(self, interaction: discord.Interaction) -> None:
        slots = parse_panel_slots(self.vagas.value)
        if slots is None:
            await interaction.response.send_message(
                "Vagas inválidas — escolhe um número de **1** a **4**.",
                ephemeral=True,
            )
            return

        party_code = self.codigo.value.strip().upper() if self.codigo.value.strip() else None
        if interaction.user is None:
            await interaction.response.send_message("Comando só no servidor.", ephemeral=True)
            return

        await interaction.response.send_message(
            rank_extras_prompt(slots=slots, party_code=party_code),
            view=PanelRankExtrasView(
                self._panel,
                slots=slots,
                party_code=party_code,
                user_id=interaction.user.id,
            ),
            ephemeral=True,
        )


class CreateGroupPanelView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)
        create_btn = discord.ui.Button(
            label="Criar grupo",
            style=discord.ButtonStyle.primary,
            custom_id=PANEL_BUTTON_CUSTOM_ID,
        )
        create_btn.callback = self._on_create
        self.add_item(create_btn)
        self.bot: commands.Bot | None = None
        self.settings: Settings | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
        self.event_bus: EventBus | None = None
        self.guild_config: GuildConfigService | None = None

    def bind(
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

    async def _on_create(self, interaction: discord.Interaction) -> None:
        if (
            self.bot is None
            or self.settings is None
            or self.session_factory is None
            or self.guild_config is None
        ):
            await interaction.response.send_message(
                "Bot em arranque. Tenta outra vez.",
                ephemeral=True,
            )
            return
        guild_id = interaction.guild.id if interaction.guild else None
        allowed = interaction.channel_id is not None and await channel_allowed_async(
            self.guild_config,
            self.session_factory,
            guild_id,
            interaction.channel_id,
        )
        if interaction.channel_id is None or not allowed:
            await interaction.response.send_message(
                "Este painel só funciona nos canais LFG configurados.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(CreateGroupModal(self))


def register_create_panel_view(
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> None:
    view = CreateGroupPanelView()
    view.bind(bot, settings, session_factory, event_bus, guild_config)
    bot.add_view(view)


async def publish_panel_message_bound(
    bot: commands.Bot,
    channel: discord.TextChannel,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
    *,
    replace_previous: bool = True,
) -> discord.Message:
    channel_id = channel.id
    if replace_previous:
        async with session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(LfgPanelPost).where(LfgPanelPost.channel_id == channel_id)
                )
                row = result.scalar_one_or_none()
                if row is not None:
                    try:
                        old = await channel.fetch_message(row.message_id)
                        await old.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass

    view = CreateGroupPanelView()
    view.bind(bot, settings, session_factory, event_bus, guild_config)
    guild_id = channel.guild.id if channel.guild is not None else None
    panel_embed = await _panel_embed_for_guild(session_factory, guild_config, guild_id)
    message = await channel.send(embed=panel_embed, view=view)

    async with session_factory() as session:
        async with session.begin():
            result = await session.execute(
                select(LfgPanelPost).where(LfgPanelPost.channel_id == channel_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                session.add(LfgPanelPost(channel_id=channel_id, message_id=message.id))
            else:
                row.message_id = message.id

    return message


async def resolve_lfg_text_channel(
    bot: commands.Bot, channel_id: int
) -> discord.TextChannel | None:
    channel = bot.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return channel
    for guild in bot.guilds:
        maybe = guild.get_channel(channel_id)
        if isinstance(maybe, discord.TextChannel):
            return maybe
    try:
        fetched = await bot.fetch_channel(channel_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return None
    if isinstance(fetched, discord.TextChannel):
        return fetched
    return None


async def _ensure_panel_in_channel(
    bot: commands.Bot,
    channel: discord.TextChannel,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> bool:
    """Garante painel válido no canal. Devolve True se publicou ou atualizou."""
    channel_id = channel.id
    needs_post = True
    async with session_factory() as session:
        result = await session.execute(
            select(LfgPanelPost).where(LfgPanelPost.channel_id == channel_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            try:
                msg = await channel.fetch_message(row.message_id)
                if msg.author.id == bot.user.id and is_panel_message(msg, bot.user.id):
                    needs_post = False
                    guild_id = channel.guild.id if channel.guild is not None else None
                    panel_embed = await _panel_embed_for_guild(
                        session_factory, guild_config, guild_id
                    )
                    try:
                        await msg.edit(embed=panel_embed)
                        logger.info(
                            "painel LFG: embed atualizado no canal %s",
                            channel_id,
                        )
                        return True
                    except discord.HTTPException:
                        logger.exception(
                            "painel LFG: falha ao atualizar embed no canal %s",
                            channel_id,
                        )
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                needs_post = True

    if needs_post:
        await publish_panel_message_bound(
            bot,
            channel,
            settings,
            session_factory,
            event_bus,
            guild_config,
            replace_previous=False,
        )
        logger.info("painel LFG publicado no canal %s", channel_id)
        return True
    return False


async def ensure_guild_lfg_panels(
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
    guild_id: int,
) -> int:
    """Publica/atualiza painéis nos canais LFG do servidor (se sticky ativo na BD)."""
    async with session_factory() as session:
        cfg = await guild_config.get_config(session, guild_id)
    if not cfg.panel_sticky_enabled or not cfg.lfg_channel_ids:
        return 0

    posted = 0
    for channel_id in cfg.lfg_channel_ids:
        channel = await resolve_lfg_text_channel(bot, channel_id)
        if channel is None or channel.guild is None or channel.guild.id != guild_id:
            logger.warning("painel LFG: canal %s inválido para o servidor %s", channel_id, guild_id)
            continue
        try:
            if await _ensure_panel_in_channel(
                bot, channel, settings, session_factory, event_bus, guild_config
            ):
                posted += 1
        except discord.HTTPException:
            logger.exception("falha ao publicar painel LFG no canal %s", channel_id)
    return posted


async def ensure_lfg_panels(
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    guild_config: GuildConfigService,
) -> None:
    channel_ids = await collect_lfg_channel_ids(settings, session_factory, guild_config)
    if not channel_ids:
        return

    for channel_id in channel_ids:
        channel = await resolve_lfg_text_channel(bot, channel_id)
        if channel is None:
            logger.warning("painel LFG: canal %s não encontrado ou não é texto", channel_id)
            continue

        try:
            await _ensure_panel_in_channel(
                bot, channel, settings, session_factory, event_bus, guild_config
            )
        except discord.HTTPException:
            logger.exception("falha ao publicar painel LFG no canal %s", channel_id)


class PanelStickyManager:
    """Republica o painel LFG quando deixa de ser a última mensagem do canal."""

    def __init__(self, cooldown_seconds: float) -> None:
        self._cooldown = max(5.0, cooldown_seconds)
        self._last_bump: dict[int, float] = {}
        self._locks: dict[int, asyncio.Lock] = {}
        self._scheduled: dict[int, asyncio.Task[None]] = {}

    def _lock_for(self, channel_id: int) -> asyncio.Lock:
        lock = self._locks.get(channel_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[channel_id] = lock
        return lock

    async def notify_channel_activity(
        self,
        bot: commands.Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        message: discord.Message,
        guild_config: GuildConfigService,
    ) -> None:
        if message.guild is None or not isinstance(message.channel, discord.TextChannel):
            return
        runtime = await guild_config.get_config_for_factory(session_factory, message.guild.id)
        if not runtime.panel_sticky_enabled:
            return
        if not await channel_allowed_async(
            guild_config, session_factory, message.guild.id, message.channel.id
        ):
            return
        bot_id = bot.user.id if bot.user else None
        if is_panel_message(message, bot_id):
            return
        await self._ensure_bump_scheduled(
            bot, settings, session_factory, event_bus, message.channel, guild_config
        )

    async def notify_after_lobby_post(
        self,
        bot: commands.Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        channel: discord.TextChannel,
        guild_config: GuildConfigService,
    ) -> None:
        if channel.guild is None:
            return
        runtime = await guild_config.get_config_for_factory(session_factory, channel.guild.id)
        if not runtime.panel_sticky_enabled:
            return
        if not await channel_allowed_async(
            guild_config, session_factory, channel.guild.id, channel.id
        ):
            return
        await self._ensure_bump_scheduled(
            bot, settings, session_factory, event_bus, channel, guild_config
        )

    async def _ensure_bump_scheduled(
        self,
        bot: commands.Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        channel: discord.TextChannel,
        guild_config: GuildConfigService,
    ) -> None:
        channel_id = channel.id
        existing = self._scheduled.get(channel_id)
        if existing is not None and not existing.done():
            return

        now = time.monotonic()
        elapsed = now - self._last_bump.get(channel_id, 0.0)
        delay = max(0.0, self._cooldown - elapsed)

        async def runner() -> None:
            try:
                if delay > 0:
                    await asyncio.sleep(delay)
                await self._bump_if_needed(
                    bot, settings, session_factory, event_bus, channel, guild_config
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("sticky painel LFG falhou no canal %s", channel_id)
            finally:
                self._scheduled.pop(channel_id, None)

        self._scheduled[channel_id] = asyncio.create_task(runner())

    async def _bump_if_needed(
        self,
        bot: commands.Bot,
        settings: Settings,
        session_factory: async_sessionmaker[AsyncSession],
        event_bus: EventBus,
        channel: discord.TextChannel,
        guild_config: GuildConfigService,
    ) -> None:
        channel_id = channel.id
        lock = self._lock_for(channel_id)
        async with lock:
            async with session_factory() as session:
                result = await session.execute(
                    select(LfgPanelPost).where(LfgPanelPost.channel_id == channel_id)
                )
                row = result.scalar_one_or_none()
            if row is None:
                return

            history = [msg async for msg in channel.history(limit=1)]
            if history and history[0].id == row.message_id:
                return

            try:
                await publish_panel_message_bound(
                    bot,
                    channel,
                    settings,
                    session_factory,
                    event_bus,
                    guild_config,
                    replace_previous=True,
                )
                self._last_bump[channel_id] = time.monotonic()
                logger.debug("sticky painel LFG reposto no canal %s", channel_id)
            except discord.HTTPException:
                logger.exception("sticky painel LFG: falha ao republicar no canal %s", channel_id)


_sticky_manager: PanelStickyManager | None = None


def get_panel_sticky_manager(settings: Settings) -> PanelStickyManager:
    global _sticky_manager
    if _sticky_manager is None:
        _sticky_manager = PanelStickyManager(settings.panel_sticky_cooldown_seconds)
    return _sticky_manager


async def notify_panel_sticky_activity(
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    message: discord.Message,
    guild_config: GuildConfigService,
) -> None:
    await get_panel_sticky_manager(settings).notify_channel_activity(
        bot, settings, session_factory, event_bus, message, guild_config
    )


async def notify_panel_sticky_after_lobby(
    bot: commands.Bot,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    event_bus: EventBus,
    channel: discord.TextChannel,
    guild_config: GuildConfigService | None = None,
) -> None:
    if guild_config is None:
        return
    await get_panel_sticky_manager(settings).notify_after_lobby_post(
        bot, settings, session_factory, event_bus, channel, guild_config
    )
