import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  api,
  DiscordChannel,
  DiscordRole,
  Guild,
  GuildSettings,
  GuildStats,
  ImmuneEmbedTier,
  MAX_IMMUNE_EMBED_TIERS,
  RoleMapping,
  User,
  ValorantAgent,
  ValorantAgentRoleMapping,
  normalizeGuildSettings,
  unionImmuneRoleIds,
} from "./api";
import { RoleMultiSearchSelect, RoleSearchSelect } from "./RoleSearchSelect";
import {
  ADMIN_SECTIONS,
  EMBED_PEDIDOS_TABS,
  EMBED_TABS,
  EMBED_TEXT_FIELDS,
  EMBED_TEXT_SECTIONS,
  defaultEmbedText,
  effectiveEmbedText,
  isEmbedTextCustomized,
  type AdminSection,
  type EmbedPedidosTab,
  type EmbedTab,
} from "./embedAdminConfig";
import { EmbedTextFieldRow } from "./components/EmbedTextFieldRow";

const RANKS = [
  "Unranked",
  "Iron",
  "Bronze",
  "Silver",
  "Gold",
  "Platinum",
  "Diamond",
  "Ascendant",
  "Immortal",
  "Radiant",
];

const AGENTS = ["Duelist", "Initiator", "Controller", "Sentinel"];

const RANK_LABELS: Record<string, string> = {
  Unranked: "Unranked (sem ranked)",
};

const DEFAULT_RANK_EMBED_COLORS: Record<string, string> = {
  Unranked: "4A4E5A",
  Iron: "514F4A",
  Bronze: "A0715C",
  Silver: "BBC2C9",
  Gold: "ECA82E",
  Platinum: "59C9BB",
  Diamond: "B489FF",
  Ascendant: "1FA86A",
  Immortal: "B23B4B",
  Radiant: "F4E19D",
};

function rankEmbedHex(settings: GuildSettings | null | undefined, rank: string): string {
  const custom = settings?.rank_embed_colors?.[rank];
  if (custom) {
    return custom;
  }
  return DEFAULT_RANK_EMBED_COLORS[rank] ?? "4A4E5A";
}

function hexForColorInput(hex: string): string {
  const clean = hex.replace("#", "").slice(0, 6);
  return `#${clean.padEnd(6, "0")}`;
}

export function AdminApp() {
  const [user, setUser] = useState<User | null>(null);
  const [guilds, setGuilds] = useState<Guild[]>([]);
  const [selectedGuild, setSelectedGuild] = useState<string | null>(null);
  const [settings, setSettings] = useState<GuildSettings | null>(null);
  const [channels, setChannels] = useState<DiscordChannel[]>([]);
  const [roles, setRoles] = useState<DiscordRole[]>([]);
  const [mappings, setMappings] = useState<Record<string, string>>({});
  const [stats, setStats] = useState<GuildStats | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [guildLoading, setGuildLoading] = useState(false);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const [catalogAgents, setCatalogAgents] = useState<ValorantAgent[]>([]);
  const [agentValorantRoles, setAgentValorantRoles] = useState<Record<string, string>>({});
  const [catalogMeta, setCatalogMeta] = useState<string | null>(null);
  const [catalogSyncing, setCatalogSyncing] = useState(false);

  const bootstrapped = useRef(false);
  const saveNoticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const guildLoadGen = useRef(0);
  const [guildReloadToken, setGuildReloadToken] = useState(0);
  const [adminSection, setAdminSection] = useState<AdminSection>("geral");
  const [embedTab, setEmbedTab] = useState<EmbedTab>("painel");
  const [embedPedidosTab, setEmbedPedidosTab] = useState<EmbedPedidosTab>("cores");

  const selected = useMemo(
    () =>
      guilds.find((g) => String(g.id) === String(selectedGuild ?? "")) ?? null,
    [guilds, selectedGuild],
  );

  const refreshGuildList = async () => {
    setError(null);
    try {
      const list = await api.guilds();
      setGuilds(list);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Não foi possível atualizar servidores.",
      );
    }
  };

  useEffect(
    () => () => {
      if (saveNoticeTimer.current) {
        clearTimeout(saveNoticeTimer.current);
      }
    },
    [],
  );

  useEffect(() => {
    if (bootstrapped.current) {
      return;
    }
    bootstrapped.current = true;

    void (async () => {
      try {
        const me = await api.me();
        setUser(me);
        try {
          const list = await api.guilds();
          setGuilds(list);
        } catch (err) {
          setError(
            err instanceof Error
              ? err.message
              : "Não foi possível carregar os servidores.",
          );
        }
        const invite = await api.inviteUrl();
        setInviteUrl(invite.url);
        try {
          const [meta, agents] = await Promise.all([api.catalogMeta(), api.catalogAgents()]);
          setCatalogMeta(meta.last_synced_at);
          setCatalogAgents(agents);
        } catch {
          /* catálogo opcional até primeira sync */
        }
      } catch {
        setUser(null);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  useEffect(() => {
    if (!selectedGuild) {
      setSettings(null);
      setChannels([]);
      setRoles([]);
      setStats(null);
      setGuildLoading(false);
      return;
    }

    const guild = guilds.find((g) => String(g.id) === String(selectedGuild));
    if (!guild) {
      if (guilds.length > 0) {
        setGuildLoading(false);
      }
      return;
    }
    if (!guild.bot_installed) {
      setSettings(null);
      setChannels([]);
      setRoles([]);
      setStats(null);
      setGuildLoading(false);
      return;
    }

    const generation = ++guildLoadGen.current;
    setGuildLoading(true);
    setError(null);

    void (async () => {
      try {
        const s = await api.settings(selectedGuild);
        if (generation !== guildLoadGen.current) return;
        setSettings(normalizeGuildSettings(s));

        const [chRes, rlRes, mpRes, stRes, arRes] = await Promise.allSettled([
          api.channels(selectedGuild),
          api.roles(selectedGuild),
          api.roleMappings(selectedGuild),
          api.stats(selectedGuild),
          api.valorantAgentRoles(selectedGuild),
        ]);
        if (generation !== guildLoadGen.current) return;

        const partialErrors: string[] = [];
        if (chRes.status === "fulfilled") {
          setChannels(chRes.value);
        } else {
          setChannels([]);
          partialErrors.push("lista de canais");
        }
        if (rlRes.status === "fulfilled") {
          setRoles(rlRes.value);
        } else {
          setRoles([]);
          partialErrors.push("lista de roles");
        }
        if (mpRes.status === "fulfilled") {
          const map: Record<string, string> = {};
          for (const item of mpRes.value) {
            map[`${item.mapping_type}:${item.logical_key}`] = item.discord_role_id;
          }
          setMappings(map);
        }
        if (stRes.status === "fulfilled") {
          setStats(stRes.value);
        } else {
          setStats(null);
        }
        if (arRes.status === "fulfilled") {
          const map: Record<string, string> = {};
          for (const row of arRes.value) {
            map[row.agent_uuid] = row.discord_role_id;
          }
          setAgentValorantRoles(map);
        }

        if (partialErrors.length > 0) {
          setError(
            `Configuração carregada, mas falhou a obter ${partialErrors.join(" e ")}. ` +
              "Confirma que o bot está no servidor e tem permissão Ver canais / Ver roles.",
          );
        }
      } catch (err) {
        if (generation !== guildLoadGen.current) return;
        setSettings(null);
        setError(err instanceof Error ? err.message : "Erro ao carregar servidor.");
      } finally {
        if (generation === guildLoadGen.current) {
          setGuildLoading(false);
        }
      }
    })();

    return () => {
      guildLoadGen.current += 1;
    };
  }, [selectedGuild, guilds, guildReloadToken]);

  const patchSettings = (patch: Partial<GuildSettings>) => {
    setSaveNotice(null);
    setSettings((prev) => normalizeGuildSettings({ ...(prev ?? {}), ...patch }));
  };

  const patchEmbedText = (key: string, value: string) => {
    if (!settings) return;
    const field = EMBED_TEXT_FIELDS.find((f) => f.key === key);
    const max = field?.max ?? 4096;
    const next = { ...(settings.lfg_embed_custom_texts ?? {}) };
    const trimmed = value.trim().slice(0, max);
    const defaultVal = defaultEmbedText(key).trim();
    if (!trimmed || trimmed === defaultVal) {
      delete next[key];
    } else {
      next[key] = trimmed;
    }
    patchSettings({ lfg_embed_custom_texts: next });
  };

  const resetEmbedText = (key: string) => {
    patchEmbedText(key, defaultEmbedText(key));
  };

  const patchImmuneTiers = (tiers: ImmuneEmbedTier[]) => {
    patchSettings({
      immune_embed_tiers: tiers,
      immune_role_ids: unionImmuneRoleIds(tiers),
    });
  };

  const updateImmuneTier = (index: number, patch: Partial<ImmuneEmbedTier>) => {
    if (!settings) return;
    const tiers = [...settings.immune_embed_tiers];
    tiers[index] = { ...tiers[index], ...patch };
    patchImmuneTiers(tiers);
  };

  const moveImmuneTier = (index: number, direction: -1 | 1) => {
    if (!settings) return;
    const target = index + direction;
    if (target < 0 || target >= settings.immune_embed_tiers.length) return;
    const tiers = [...settings.immune_embed_tiers];
    const [item] = tiers.splice(index, 1);
    tiers.splice(target, 0, item);
    patchImmuneTiers(tiers);
  };

  const removeImmuneTier = (index: number) => {
    if (!settings) return;
    const tiers = settings.immune_embed_tiers.filter((_, i) => i !== index);
    patchImmuneTiers(tiers);
  };

  const addImmuneTier = () => {
    if (!settings) return;
    if (settings.immune_embed_tiers.length >= MAX_IMMUNE_EMBED_TIERS) return;
    const n = settings.immune_embed_tiers.length + 1;
    patchImmuneTiers([
      ...settings.immune_embed_tiers,
      {
        label: n === 1 ? "Pedido em destaque" : `Nível ${n}`,
        color: "FFD700",
        role_ids: [],
      },
    ]);
  };

  const showSaveSuccess = (message: string) => {
    setSaveNotice(message);
    if (saveNoticeTimer.current) {
      clearTimeout(saveNoticeTimer.current);
    }
    saveNoticeTimer.current = setTimeout(() => {
      setSaveNotice(null);
      saveNoticeTimer.current = null;
    }, 5000);
  };

  const toggleChannel = (id: string) => {
    if (!settings) return;
    const set = new Set(settings.lfg_channel_ids);
    if (set.has(id)) set.delete(id);
    else set.add(id);
    patchSettings({ lfg_channel_ids: [...set] });
  };

  const saveSettings = async () => {
    if (!selectedGuild || !settings) return;
    setSaving(true);
    setError(null);
    setSaveNotice(null);
    try {
      const saved = await api.patchSettings(selectedGuild, settings);
      setSettings(normalizeGuildSettings(saved));
      const mappingList: RoleMapping[] = [];
      for (const rank of RANKS) {
        const id = mappings[`valorant_rank:${rank}`];
        if (id) {
          mappingList.push({
            mapping_type: "valorant_rank",
            logical_key: rank,
            discord_role_id: id,
          });
        }
      }
      for (const agent of AGENTS) {
        const id = mappings[`agent_role:${agent}`];
        if (id) {
          mappingList.push({
            mapping_type: "agent_role",
            logical_key: agent,
            discord_role_id: id,
          });
        }
      }
      await api.putRoleMappings(selectedGuild, mappingList);
      const valorantMappings: ValorantAgentRoleMapping[] = [];
      for (const [agentUuid, roleId] of Object.entries(agentValorantRoles)) {
        if (roleId) {
          valorantMappings.push({ agent_uuid: agentUuid, discord_role_id: roleId });
        }
      }
      await api.putValorantAgentRoles(selectedGuild, valorantMappings);
      setStats(await api.stats(selectedGuild));
      showSaveSuccess("Configuração guardada com sucesso.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível guardar.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="app-shell">
        <div className="fullscreen-main admin-main">
          <p className="hint">A carregar…</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="app-shell">
        <div className="fullscreen-main admin-main admin-main--center">
          <h1>LFG Valorant</h1>
          <p className="sub">Configura canais e roles do bot por servidor Discord.</p>
          <div className="card row">
            <a className="btn" href="/auth/discord/login">Entrar com Discord</a>
          </div>
        </div>
      </div>
    );
  }

  const syncCatalog = async () => {
    setCatalogSyncing(true);
    setError(null);
    try {
      await api.syncCatalog();
      const [meta, agents] = await Promise.all([api.catalogMeta(), api.catalogAgents()]);
      setCatalogMeta(meta.last_synced_at);
      setCatalogAgents(agents);
      showSaveSuccess("Catálogo Valorant sincronizado.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Falha ao sincronizar catálogo.");
    } finally {
      setCatalogSyncing(false);
    }
  };

  return (
    <div className="app-shell app-shell--site">
      <header className="app-shell__nav">
        <Link to="/" className="app-shell__brand">LFG Valorant</Link>
        <nav className="app-shell__links">
          <Link to="/me">Meu perfil</Link>
          <span className="app-shell__active">Admin</span>
          <button
            type="button"
            className="btn-ghost"
            onClick={() => void api.logout().then(() => window.location.reload())}
          >
            Sair
          </button>
        </nav>
      </header>
      <div className="app-shell__main fullscreen-main admin-main">
      <div className="admin-toolbar row">
        <div>
          <h1>Olá, {user.username}</h1>
          <p className="sub">
            {selected && guildLoading
              ? `A carregar «${selected.name}»…`
              : selected && settings
                ? `Servidor: ${selected.name}`
                : "Escolhe um servidor onde tens permissão de gerir."}
          </p>
        </div>
      </div>

      <div className="card">
        <div className="row">
          <label>
            Servidor
            <select
              value={selectedGuild ?? ""}
              onChange={(e) => {
                setError(null);
                setSelectedGuild(e.target.value || null);
              }}
            >
              <option value="">— selecionar —</option>
              {guilds.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                  {g.bot_installed ? "" : " (bot ausente)"}
                </option>
              ))}
            </select>
          </label>
          {inviteUrl && (
            <a className="btn secondary" href={inviteUrl} target="_blank" rel="noreferrer">
              Adicionar bot a um servidor
            </a>
          )}
          <button type="button" className="secondary" onClick={() => void refreshGuildList()}>
            Atualizar lista
          </button>
        </div>
      </div>

      {selected && !selected.bot_installed && (
        <div className="card error-card">
          <h2>Bot ausente neste servidor</h2>
          <p>
            Escolheste <strong>{selected.name}</strong>, mas o bot ainda não está aí. Clica em{" "}
            <strong>Adicionar bot a um servidor</strong>, convida-o para este Discord e
            recarrega esta página (Ctrl+F5). Só depois aparecem canais LFG e Opções.
          </p>
          {inviteUrl && (
            <a className="btn" href={inviteUrl} target="_blank" rel="noreferrer">
              Adicionar bot agora
            </a>
          )}
        </div>
      )}

      {selectedGuild && guilds.length > 0 && !selected && (
        <p className="error">
          Não foi possível identificar o servidor selecionado. Recarrega a página (Ctrl+F5).
        </p>
      )}

      {guildLoading && selectedGuild && (
        <p className="sub">A carregar configuração do servidor…</p>
      )}

      {selected?.bot_installed &&
        selectedGuild &&
        !guildLoading &&
        !settings &&
        !error && (
          <div className="card">
            <p>
              Não foi possível mostrar a configuração. Tenta de novo ou atualiza a lista de
              servidores.
            </p>
            <button
              type="button"
              className="secondary"
              onClick={() => setGuildReloadToken((n) => n + 1)}
            >
              Recarregar configuração
            </button>
          </div>
        )}

      {error && <p className="error">{error}</p>}

      {settings && selectedGuild && (
        <div className="admin-layout">
          <nav className="admin-side-nav" aria-label="Secções da configuração">
            {ADMIN_SECTIONS.map((section) => (
              <button
                key={section.id}
                type="button"
                className={adminSection === section.id ? "active" : undefined}
                onClick={() => setAdminSection(section.id)}
              >
                <span className="admin-side-nav__label">{section.label}</span>
                <span className="admin-side-nav__hint">{section.hint}</span>
              </button>
            ))}
          </nav>

          <div className="admin-content">
          {adminSection === "geral" && (
          <>
          <div className="card" id="canais-lfg">
            <h2>Canais LFG</h2>
            {channels.length === 0 ? (
              <p className="hint">
                O bot não vê nenhum canal de texto neste servidor. Verifica se está no
                servidor e se tem permissões <strong>Ver canais</strong> e{" "}
                <strong>Ler histórico</strong>.
              </p>
            ) : (
              <div className="channel-list">
                {channels.map((ch) => (
                  <label key={ch.id}>
                    <input
                      type="checkbox"
                      checked={settings.lfg_channel_ids.includes(ch.id)}
                      onChange={() => toggleChannel(ch.id)}
                    />
                    #{ch.name}
                  </label>
                ))}
              </div>
            )}
          </div>

          <div className="card" id="opcoes">
            <h2>Opções</h2>
            <div className="row">
              <label>
                <input
                  type="checkbox"
                  checked={settings.auto_format_messages}
                  onChange={(e) =>
                    patchSettings({ auto_format_messages: e.target.checked })
                  }
                />
                Auto-format no chat
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.gamification_enabled}
                  onChange={(e) =>
                    patchSettings({ gamification_enabled: e.target.checked })
                  }
                />
                Gamificação
              </label>
              <label>
                <input
                  type="checkbox"
                  checked={settings.panel_sticky_enabled}
                  onChange={(e) =>
                    patchSettings({ panel_sticky_enabled: e.target.checked })
                  }
                />
                Painel sticky (repor «Criar grupo» no fundo)
              </label>
            </div>
            <p className="hint">
              Com isto ativo e canais LFG escolhidos, ao <strong>guardar</strong> o bot
              publica o painel «Criar grupo» nesses canais (se ainda não existir). Quando
              alguém escreve ou publica um LFG, o painel volta a aparecer no fim do canal
              (~30 s). Também podes usar <code>/lfg-painel</code> no Discord.
            </p>
            <div className="options-grid" style={{ marginTop: "0.75rem" }}>
              <label className="field-stack">
                TTL (min)
                <input
                  type="number"
                  min={5}
                  max={240}
                  value={settings.lobby_ttl_minutes}
                  onChange={(e) =>
                    patchSettings({ lobby_ttl_minutes: Number(e.target.value) })
                  }
                />
              </label>
              <label className="field-stack">
                Canal de ranking
                <select
                  value={settings.stats_channel_id || ""}
                  onChange={(e) =>
                    patchSettings({ stats_channel_id: e.target.value || "0" })
                  }
                >
                  <option value="">Todos os LFG</option>
                  {channels.map((ch) => (
                    <option key={ch.id} value={ch.id}>
                      #{ch.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="hint">
              Com um canal de ranking escolhido, o <code>/ranking</code> funciona aí e o
              ranking automático (se a gamificação estiver ativa) publica só nesse canal.
              «Todos os LFG» = ranking em qualquer canal LFG.
            </p>
          </div>

          <div className="card highlight-card" id="auditoria">
            <h2>Auditoria (canal de logs)</h2>
            <p className="hint">
              Embeds no Discord apenas — nada é guardado na base de dados. Escolhe um canal
              de texto onde o bot pode enviar mensagens.
            </p>
            <label className="field-stack">
              Canal de logs
              <select
                value={settings.log_channel_id || "0"}
                onChange={(e) =>
                  patchSettings({ log_channel_id: e.target.value || "0" })
                }
              >
                <option value="0">Desligado</option>
                {channels.map((ch) => (
                  <option key={ch.id} value={ch.id}>
                    #{ch.name}
                  </option>
                ))}
              </select>
            </label>
            <p className="hint">
              Eventos: pedidos criados/fechados/expirados, expulsões, RGPD e alterações
              guardadas neste dashboard.
            </p>
          </div>

          <div className="card highlight-card">
            <h2>Canal do guia</h2>
            <p className="hint">
              Mensagem fixa com instruções de uso (painel <strong>Criar grupo</strong>,{" "}
              <code>/procurar</code>, etc.). Ao <strong>guardar</strong> canal ou texto, o bot
              publica ou atualiza a embed. Também: <code>/lfg-guia</code> no Discord.
            </p>
            <label className="field-stack">
              Canal do guia
              <select
                value={settings.guide_channel_id || "0"}
                onChange={(e) =>
                  patchSettings({ guide_channel_id: e.target.value || "0" })
                }
              >
                <option value="0">Desligado</option>
                {channels.map((ch) => (
                  <option key={ch.id} value={ch.id}>
                    #{ch.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field-stack" style={{ marginTop: "0.75rem" }}>
              Texto do guia (Markdown Discord)
              <textarea
                rows={12}
                placeholder="Vazio = texto por defeito (resumo painel, /procurar, sem chat +2)."
                value={settings.guide_body ?? ""}
                onChange={(e) =>
                  patchSettings({
                    guide_body: e.target.value.trim() ? e.target.value : null,
                  })
                }
              />
            </label>
            <button
              type="button"
              style={{ marginTop: "0.5rem" }}
              disabled={!selectedGuild || settings.guide_channel_id === "0"}
              onClick={() => {
                if (!selectedGuild) return;
                void api.publishGuildGuide(selectedGuild).then(
                  () => setSaveNotice("Guia republicado no Discord."),
                  (err: Error) => setSaveNotice(err.message),
                );
              }}
            >
              Republicar guia agora
            </button>
          </div>

          <div className="card">
            <h2>Histórico antes do bot</h2>
            <p className="hint">
              Números do canal antigo (não são linhas falsas na BD). Somam-se aos pedidos reais
              registados pelo bot em «Desde sempre» nas métricas. <strong>Entradas</strong> = vezes
              que alguém carregou <strong>Entrar</strong> num pedido (não é o mesmo que pedidos
              criados).
            </p>
            <div className="options-grid">
              <label className="field-stack">
                Pedidos (legado)
                <input
                  type="number"
                  min={0}
                  value={settings.stats_legacy_lobbies_created}
                  onChange={(e) =>
                    patchSettings({
                      stats_legacy_lobbies_created: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label className="field-stack">
                Entradas (legado)
                <input
                  type="number"
                  min={0}
                  value={settings.stats_legacy_joins}
                  onChange={(e) =>
                    patchSettings({ stats_legacy_joins: Number(e.target.value) })
                  }
                />
              </label>
              <label className="field-stack">
                Utilizadores (legado)
                <input
                  type="number"
                  min={0}
                  value={settings.stats_legacy_users}
                  onChange={(e) =>
                    patchSettings({ stats_legacy_users: Number(e.target.value) })
                  }
                />
              </label>
            </div>
          </div>
          </>
          )}

          {adminSection === "mapeamentos" && (
          <>
          <div className="card">
            <h2>Mapeamento de ranks</h2>
            <p className="hint">
              Inclui <strong>Unranked</strong> para quem não joga ranked. O bot usa estas
              roles para detetar rank e mostrar menções nos embeds.
            </p>
            <table className="mapping-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Role Discord</th>
                </tr>
              </thead>
              <tbody>
                {RANKS.map((rank) => (
                  <tr key={rank} className={rank === "Unranked" ? "rank-row-unranked" : undefined}>
                    <td>{RANK_LABELS[rank] ?? rank}</td>
                    <td>
                      <RoleSearchSelect
                        roles={roles}
                        value={mappings[`valorant_rank:${rank}`] || ""}
                        placeholder="—"
                        onChange={(roleId) =>
                          setMappings((prev) => {
                            const next = { ...prev };
                            const key = `valorant_rank:${rank}`;
                            if (roleId === "") delete next[key];
                            else next[key] = roleId;
                            return next;
                          })
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <h2>Mapeamento de papéis (embeds)</h2>
            <table className="mapping-table">
              <thead>
                <tr>
                  <th>Papel</th>
                  <th>Role Discord</th>
                </tr>
              </thead>
              <tbody>
                {AGENTS.map((agent) => (
                  <tr key={agent}>
                    <td>{agent}</td>
                    <td>
                      <RoleSearchSelect
                        roles={roles}
                        value={mappings[`agent_role:${agent}`] || ""}
                        placeholder="—"
                        onChange={(roleId) =>
                          setMappings((prev) => {
                            const next = { ...prev };
                            const key = `agent_role:${agent}`;
                            if (roleId === "") delete next[key];
                            else next[key] = roleId;
                            return next;
                          })
                        }
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          </>
          )}

          {adminSection === "catalogo" && (
          <div className="card" id="catalogo">
            <h2>Catálogo Valorant (perfis)</h2>
            <p className="hint">
              Dados guardados na base de dados. A API externa só corre aqui ou no job de 24 h.
              {catalogMeta && (
                <>
                  {" "}
                  Última sync: <time dateTime={catalogMeta}>{new Date(catalogMeta).toLocaleString("pt-PT")}</time>
                </>
              )}
            </p>
            <button
              type="button"
              className="btn"
              disabled={catalogSyncing}
              onClick={() => void syncCatalog()}
            >
              {catalogSyncing ? "A sincronizar…" : "Sincronizar catálogo"}
            </button>
            <h3>Agente → role Discord (perfil do jogador)</h3>
            <p className="hint">
              O site não lista o catálogo inteiro ao público. Sincroniza as imagens aqui e associa
              cada agente à role que o membro tem no Discord; no perfil só aparecem os agentes
              mapeados neste servidor.
            </p>
            {catalogAgents.length === 0 ? (
              <p className="hint">Sincroniza o catálogo para mapear agentes.</p>
            ) : (
              <table className="mapping-table">
                <thead>
                  <tr>
                    <th>Agente</th>
                    <th>Role Discord</th>
                  </tr>
                </thead>
                <tbody>
                  {catalogAgents.map((agent) => (
                    <tr key={agent.uuid}>
                      <td>{agent.display_name}</td>
                      <td>
                        <RoleSearchSelect
                          roles={roles}
                          value={agentValorantRoles[agent.uuid] || ""}
                          placeholder="—"
                          onChange={(roleId) =>
                            setAgentValorantRoles((prev) => {
                              const next = { ...prev };
                              if (roleId === "") delete next[agent.uuid];
                              else next[agent.uuid] = roleId;
                              return next;
                            })
                          }
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          )}

          {adminSection === "embeds" && (
          <div className="card">
            <h2>Embeds LFG</h2>
            <p className="hint">
              São <strong>dois embeds diferentes</strong>: o painel fixo «Criar grupo» no
              canal e o embed de cada pedido publicado. Configura cada um na sua aba.
            </p>
            <nav className="embed-subnav embed-subnav--main" aria-label="Tipo de embed">
              {EMBED_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={embedTab === tab.id ? "active" : undefined}
                  onClick={() => setEmbedTab(tab.id)}
                >
                  <span>{tab.label}</span>
                  <span className="embed-subnav__hint">{tab.hint}</span>
                </button>
              ))}
            </nav>

            {embedTab === "painel" && (
            <>
            <p className="hint embed-text-intro">
              Mensagem permanente com o botão <strong>Criar grupo</strong>. Não confundir
              com os pedidos que aparecem quando alguém publica.
            </p>
            <div className="embed-media-grid embed-panel-style">
              <label>
                Cor da barra lateral
                <div className="rank-color-row">
                  <input
                    type="color"
                    value={hexForColorInput(settings.lfg_panel_color ?? "FF4655")}
                    onChange={(e) =>
                      patchSettings({
                        lfg_panel_color: e.target.value.replace("#", "").toUpperCase(),
                      })
                    }
                  />
                  <code>#{settings.lfg_panel_color}</code>
                </div>
              </label>
              <label>
                Marca no rodapé (opcional)
                <input
                  type="text"
                  maxLength={64}
                  value={settings.lfg_panel_footer_brand ?? ""}
                  placeholder={`Vazio = ${settings.lfg_embed_footer_brand ?? "LFG Valorant"}`}
                  onChange={(e) =>
                    patchSettings({
                      lfg_panel_footer_brand: e.target.value.trim() || null,
                    })
                  }
                />
              </label>
              <label>
                Banner do painel (URL)
                <input
                  type="url"
                  value={settings.lfg_panel_banner_url ?? ""}
                  onChange={(e) =>
                    patchSettings({ lfg_panel_banner_url: e.target.value.trim() || null })
                  }
                  placeholder="Vazio = banner dos pedidos (se ativo)"
                />
              </label>
              <label>
                Miniatura (URL)
                <input
                  type="url"
                  value={settings.lfg_panel_thumbnail_url ?? ""}
                  onChange={(e) =>
                    patchSettings({ lfg_panel_thumbnail_url: e.target.value.trim() || null })
                  }
                />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={settings.lfg_panel_decorative ?? true}
                  onChange={(e) =>
                    patchSettings({ lfg_panel_decorative: e.target.checked })
                  }
                />
                Estilo chamativo no painel (emoji no título, etc.)
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={settings.lfg_embed_banner_on_panel ?? true}
                  onChange={(e) =>
                    patchSettings({ lfg_embed_banner_on_panel: e.target.checked })
                  }
                />
                Se não houver banner próprio, usar o banner dos pedidos
              </label>
            </div>
            <div className="embed-text-sections">
              {EMBED_TEXT_SECTIONS.filter((s) => s.id === "painel").map((section) => (
                <section key={section.id} className="embed-text-section">
                  <h3>{section.title}</h3>
                  <p className="hint">{section.intro}</p>
                  <div className="embed-text-section__fields">
                    {EMBED_TEXT_FIELDS.filter((f) => f.group === section.id).map((field) => (
                      <EmbedTextFieldRow
                        key={field.key}
                        field={field}
                        value={effectiveEmbedText(
                          settings.lfg_embed_custom_texts ?? {},
                          field.key,
                        )}
                        isCustomized={isEmbedTextCustomized(
                          settings.lfg_embed_custom_texts ?? {},
                          field.key,
                        )}
                        onChange={(v) => patchEmbedText(field.key, v)}
                        onReset={() => resetEmbedText(field.key)}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
            </>
            )}

            {embedTab === "pedidos" && (
            <>
            <nav className="embed-subnav" aria-label="Pedidos publicados">
              {EMBED_PEDIDOS_TABS.map((tab) => (
                <button
                  key={tab.id}
                  type="button"
                  className={embedPedidosTab === tab.id ? "active" : undefined}
                  onClick={() => setEmbedPedidosTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </nav>

            {embedPedidosTab === "cores" && (
            <>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={settings.lfg_embed_decorative ?? true}
                onChange={(e) => patchSettings({ lfg_embed_decorative: e.target.checked })}
              />
              Estilo chamativo nos pedidos (emojis, barra de vagas 🟥)
            </label>
            <div className="embed-theme-grid">
              <label>
                Cor Competitivo
                <div className="rank-color-row">
                  <input
                    type="color"
                    value={hexForColorInput(settings.lfg_embed_competitive_color)}
                    onChange={(e) =>
                      patchSettings({
                        lfg_embed_competitive_color: e.target.value.replace("#", "").toUpperCase(),
                      })
                    }
                  />
                  <code>#{settings.lfg_embed_competitive_color}</code>
                </div>
              </label>
              <label>
                Cor Unrated
                <div className="rank-color-row">
                  <input
                    type="color"
                    value={hexForColorInput(settings.lfg_embed_unrated_color)}
                    onChange={(e) =>
                      patchSettings({
                        lfg_embed_unrated_color: e.target.value.replace("#", "").toUpperCase(),
                      })
                    }
                  />
                  <code>#{settings.lfg_embed_unrated_color}</code>
                </div>
              </label>
              <label>
                Cor lobby cheio
                <div className="rank-color-row">
                  <input
                    type="color"
                    value={hexForColorInput(settings.lfg_embed_full_color)}
                    onChange={(e) =>
                      patchSettings({
                        lfg_embed_full_color: e.target.value.replace("#", "").toUpperCase(),
                      })
                    }
                  />
                  <code>#{settings.lfg_embed_full_color}</code>
                </div>
              </label>
              <label>
                Cor fechado / expirado
                <div className="rank-color-row">
                  <input
                    type="color"
                    value={hexForColorInput(settings.lfg_embed_inactive_color)}
                    onChange={(e) =>
                      patchSettings({
                        lfg_embed_inactive_color: e.target.value.replace("#", "").toUpperCase(),
                      })
                    }
                  />
                  <code>#{settings.lfg_embed_inactive_color}</code>
                </div>
              </label>
            </div>
            <label>
              Cor da barra por
              <select
                value={settings.lfg_embed_color_source ?? "mode"}
                onChange={(e) =>
                  patchSettings({
                    lfg_embed_color_source: e.target
                      .value as GuildSettings["lfg_embed_color_source"],
                  })
                }
              >
                <option value="mode">Modo (Competitivo / Unrated)</option>
                <option value="host_rank">Rank do host</option>
                <option value="min_rank">Rank mínimo do pedido</option>
                <option value="max_rank">Rank máximo do pedido</option>
              </select>
            </label>
            <table className="mapping-table rank-color-table">
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Cor do embed</th>
                </tr>
              </thead>
              <tbody>
                {RANKS.map((rank) => {
                  const hex = rankEmbedHex(settings, rank);
                  return (
                    <tr key={rank}>
                      <td>{rank}</td>
                      <td>
                        <div className="rank-color-row">
                          <input
                            type="color"
                            value={hexForColorInput(hex)}
                            onChange={(e) => {
                              const value = e.target.value.replace("#", "").toUpperCase();
                              patchSettings({
                                rank_embed_colors: {
                                  ...(settings.rank_embed_colors ?? {}),
                                  [rank]: value,
                                },
                              });
                            }}
                          />
                          <code>#{hex}</code>
                          {settings.rank_embed_colors?.[rank] && (
                            <button
                              type="button"
                              className="secondary"
                              onClick={() => {
                                const next = { ...(settings.rank_embed_colors ?? {}) };
                                delete next[rank];
                                patchSettings({ rank_embed_colors: next });
                              }}
                            >
                              Padrão
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            </>
            )}

            {embedTab === "pedidos" && embedPedidosTab === "textos" && (
            <div className="embed-text-sections">
              <p className="hint embed-text-intro">
                Textos dos embeds quando alguém <strong>publica um grupo</strong> (não o
                painel fixo).
              </p>
              {EMBED_TEXT_SECTIONS.filter((s) => s.id !== "painel").map((section) => (
                <section key={section.id} className="embed-text-section">
                  <h3>{section.title}</h3>
                  <p className="hint">{section.intro}</p>
                  <div className="embed-text-section__fields">
                    {EMBED_TEXT_FIELDS.filter((f) => f.group === section.id).map((field) => (
                      <EmbedTextFieldRow
                        key={field.key}
                        field={field}
                        value={effectiveEmbedText(
                          settings.lfg_embed_custom_texts ?? {},
                          field.key,
                        )}
                        isCustomized={isEmbedTextCustomized(
                          settings.lfg_embed_custom_texts ?? {},
                          field.key,
                        )}
                        onChange={(v) => patchEmbedText(field.key, v)}
                        onReset={() => resetEmbedText(field.key)}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
            )}

            {embedTab === "pedidos" && embedPedidosTab === "midia" && (
            <div className="embed-media-grid">
              <label>
                Marca no rodapé dos pedidos
                <input
                  type="text"
                  maxLength={64}
                  value={settings.lfg_embed_footer_brand ?? "LFG Valorant"}
                  onChange={(e) => patchSettings({ lfg_embed_footer_brand: e.target.value })}
                />
              </label>
              <label>
                Banner dos pedidos (URL HTTPS)
                <input
                  type="url"
                  value={settings.lfg_embed_banner_url ?? ""}
                  onChange={(e) =>
                    patchSettings({ lfg_embed_banner_url: e.target.value.trim() || null })
                  }
                  placeholder="https://…"
                />
              </label>
              <label>
                Miniatura dos pedidos (se não houver ícone de rank)
                <input
                  type="url"
                  value={settings.lfg_embed_thumbnail_url ?? ""}
                  onChange={(e) =>
                    patchSettings({ lfg_embed_thumbnail_url: e.target.value.trim() || null })
                  }
                />
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={settings.lfg_embed_banner_on_lobby ?? true}
                  onChange={(e) =>
                    patchSettings({ lfg_embed_banner_on_lobby: e.target.checked })
                  }
                />
                Mostrar banner nos pedidos
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={settings.lfg_embed_show_author ?? true}
                  onChange={(e) => patchSettings({ lfg_embed_show_author: e.target.checked })}
                />
                Mostrar autor (host + avatar)
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={settings.lfg_embed_show_timestamp ?? true}
                  onChange={(e) =>
                    patchSettings({ lfg_embed_show_timestamp: e.target.checked })
                  }
                />
                Mostrar data/hora no embed
              </label>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={settings.lfg_embed_show_thumbnail ?? true}
                  onChange={(e) =>
                    patchSettings({ lfg_embed_show_thumbnail: e.target.checked })
                  }
                />
                Miniatura automática por rank (roles mapeadas)
              </label>
            </div>
            )}
            </>
            )}

            {embedTab === "destaque" && (
            <>
            <p className="hint">
              Os níveis de destaque configuram-se em <strong>Moderação → Roles isentas</strong>.
              Prioridade 1 = título e cor mais fortes no embed do pedido.
            </p>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={settings.immune_embed_enabled ?? true}
                onChange={(e) =>
                  patchSettings({ immune_embed_enabled: e.target.checked })
                }
              />
              Ativar embed em destaque para hosts com role isenta
            </label>
            </>
            )}
          </div>
          )}

          {adminSection === "moderacao" && (
          <>
          <div className="card">
            <h2>Penalizações ao sair de party privada</h2>
            <p className="hint">
              Quando o código da party é <strong>privado</strong>, sair voluntariamente
              bloqueia temporariamente novas pesquisas/entradas. Os contadores reiniciam
              cada dia (fuso Lisboa). Expulsões pelo host não contam.
            </p>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={settings.search_penalty_enabled ?? true}
                onChange={(e) =>
                  patchSettings({ search_penalty_enabled: e.target.checked })
                }
              />
              Ativar bloqueio temporário ao sair de party privada
            </label>
            <div className="penalty-grid">
              <label>
                1.ª–{settings.search_penalty_early_max_count ?? 3}.ª saída do dia (min)
                <input
                  type="number"
                  min={1}
                  max={1440}
                  value={settings.search_penalty_early_minutes ?? 5}
                  onChange={(e) =>
                    patchSettings({
                      search_penalty_early_minutes: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                Até à saída n.º
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={settings.search_penalty_early_max_count ?? 3}
                  onChange={(e) =>
                    patchSettings({
                      search_penalty_early_max_count: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                {(settings.search_penalty_early_max_count ?? 3) + 1}.ª saída (min)
                <input
                  type="number"
                  min={1}
                  max={1440}
                  value={settings.search_penalty_mid_minutes ?? 15}
                  onChange={(e) =>
                    patchSettings({ search_penalty_mid_minutes: Number(e.target.value) })
                  }
                />
              </label>
              <label>
                {(settings.search_penalty_early_max_count ?? 3) + 2}.ª+ saídas (horas)
                <input
                  type="number"
                  min={1}
                  max={168}
                  value={settings.search_penalty_severe_hours ?? 12}
                  onChange={(e) =>
                    patchSettings({ search_penalty_severe_hours: Number(e.target.value) })
                  }
                />
              </label>
            </div>
          </div>

          <div className="card">
            <h2>Roles isentas de moderação automática</h2>
            <p className="hint">
              Define até <strong>{MAX_IMMUNE_EMBED_TIERS} níveis</strong> (prioridade 1
              = maior destaque no embed). Cada nível tem roles, título e cor de reserva.
              Qualquer role listada conta como isenta (moderação futura e cooldown ao
              fechar pedido). Se o host tiver roles em vários níveis, aplica-se o nível
              com número mais baixo.
            </p>
            <div className="grid two">
              <label>
                Espera após fechar pedido (resto dos membros, segundos)
                <input
                  type="number"
                  min={0}
                  max={86400}
                  value={settings.host_recreate_cooldown_seconds ?? 300}
                  onChange={(e) =>
                    patchSettings({
                      host_recreate_cooldown_seconds: Number(e.target.value),
                    })
                  }
                />
              </label>
              <label>
                Espera após fechar pedido (roles isentas, segundos)
                <input
                  type="number"
                  min={0}
                  max={86400}
                  value={settings.immune_host_recreate_cooldown_seconds ?? 10}
                  onChange={(e) =>
                    patchSettings({
                      immune_host_recreate_cooldown_seconds: Number(e.target.value),
                    })
                  }
                />
              </label>
            </div>
            {settings.immune_embed_tiers.map((tier, index) => (
              <div key={index} className="card tier-card">
                <div className="row tier-card-header">
                  <h3>Prioridade {index + 1}</h3>
                  <div className="tier-actions">
                    <button
                      type="button"
                      disabled={index === 0}
                      onClick={() => moveImmuneTier(index, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      disabled={index === settings.immune_embed_tiers.length - 1}
                      onClick={() => moveImmuneTier(index, 1)}
                    >
                      ↓
                    </button>
                    <button type="button" onClick={() => removeImmuneTier(index)}>
                      Remover
                    </button>
                  </div>
                </div>
                <div className="row">
                  <label>
                    Texto do destaque (título do embed)
                    <input
                      type="text"
                      maxLength={64}
                      value={tier.label}
                      onChange={(e) =>
                        updateImmuneTier(index, { label: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    Cor de reserva (role sem cor no Discord)
                    <input
                      type="color"
                      value={hexForColorInput(tier.color)}
                      onChange={(e) =>
                        updateImmuneTier(index, {
                          color: e.target.value.replace("#", "").toUpperCase(),
                        })
                      }
                    />
                  </label>
                </div>
                <RoleMultiSearchSelect
                  roles={roles}
                  value={tier.role_ids}
                  onChange={(ids) => updateImmuneTier(index, { role_ids: ids })}
                />
              </div>
            ))}
            <button
              type="button"
              disabled={settings.immune_embed_tiers.length >= MAX_IMMUNE_EMBED_TIERS}
              onClick={addImmuneTier}
            >
              Adicionar nível (
              {settings.immune_embed_tiers.length}/{MAX_IMMUNE_EMBED_TIERS})
            </button>
          </div>
          </>
          )}

          {adminSection === "metricas" && stats && (
            <div className="card">
              <h2>Métricas ({stats.period_days} dias)</h2>
              <p className="hint">
                Janela = últimos {stats.period_days} dias (dados reais do bot). «Desde sempre»
                inclui o histórico manual do admin. «Cheio» = vagas preenchidas; «completo» =
                gamificação ao fechar.
              </p>
              <div className="stats" style={{ marginBottom: "1rem" }}>
                <div className="stat">
                  <strong>{stats.lobbies_created_lifetime}</strong>
                  Pedidos (desde sempre)
                </div>
                <div className="stat">
                  <strong>{stats.joins_lifetime}</strong>
                  Entradas (desde sempre)
                </div>
                <div className="stat">
                  <strong>{stats.users_lifetime}</strong>
                  Utilizadores (desde sempre)
                </div>
              </div>
              <p className="hint">
                Bot só: {stats.lobbies_created_bot} pedidos · {stats.joins_bot} entradas ·{" "}
                {stats.users_bot} utilizadores · legado: {stats.stats_legacy_lobbies_created} /{" "}
                {stats.stats_legacy_joins} / {stats.stats_legacy_users}
              </p>
              <div className="stats">
                <div className="stat">
                  <strong>{stats.active_lobbies}</strong>
                  Ativos agora
                </div>
                <div className="stat">
                  <strong>{stats.lobbies_created_period}</strong>
                  Pedidos criados
                </div>
                <div className="stat">
                  <strong>{stats.joins_period}</strong>
                  Entradas
                </div>
                <div className="stat">
                  <strong>{stats.active_users_7d ?? 0}</strong>
                  Utilizadores (7d)
                </div>
                <div className="stat">
                  <strong>{stats.groups_filled_period ?? 0}</strong>
                  Grupos cheios
                </div>
                <div className="stat">
                  <strong>{stats.avg_minutes_to_fill ?? 0}</strong>
                  min até cheio (média)
                </div>
              </div>
              {stats.created_by_source && (
                <p className="hint">
                  Origem dos pedidos: /procurar{" "}
                  <strong>{stats.created_by_source.slash}</strong> · painel{" "}
                  <strong>{stats.created_by_source.panel}</strong> · chat automático{" "}
                  <strong>{stats.created_by_source.chat}</strong>
                </p>
              )}
            </div>
          )}

          <div className="save-bar">
            <button type="button" disabled={saving} onClick={() => void saveSettings()}>
              {saving ? "A guardar…" : "Guardar configuração"}
            </button>
            {saveNotice && <p className="save-notice success">{saveNotice}</p>}
            {saving && <p className="save-notice pending">A enviar para o servidor…</p>}
          </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
}
